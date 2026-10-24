"""기존 Rapfi 엔진을 별도 프로세스로 실행한다. 자체 학습은 하지 않는다."""
import os
import re
import shutil
import subprocess
import tarfile
import threading
import platform
from pathlib import Path
from urllib.request import urlopen

from gomoku.rules import board_at, candidates, forbidden, validate, winning_moves, coord

REVISION = "1387d11312190ec66665d361ff07a7c70221b78a"
ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()


class EngineError(Exception):
    pass


def ensure_engine():
    configured = os.getenv("RAPFI_PATH")
    if configured:
        if not Path(configured).is_file():
            raise EngineError("RAPFI_PATH 실행 파일이 없습니다.")
        return str(Path(configured).resolve())
    target = ROOT / ".cache" / "rapfi" / "build" / "pbrain-rapfi"
    with LOCK:
        if target.is_file():
            return str(target)
        directory = target.parents[1]
        directory.mkdir(parents=True, exist_ok=True)
        archive = directory / "source.tar.gz"
        try:
            with urlopen(f"https://codeload.github.com/dotb1ue/rapfi/tar.gz/{REVISION}", timeout=60) as response:
                archive.write_bytes(response.read())
            with tarfile.open(archive) as source:
                source.extractall(directory, filter="data")
            source_dir = directory / f"rapfi-{REVISION}" / "Rapfi"
            cmake = shutil.which("cmake") or str(Path(os.sys.executable).parent / "cmake")
            command = [cmake, "-S", str(source_dir), "-B", str(target.parent),
                       "-DCMAKE_BUILD_TYPE=Release", "-DNO_COMMAND_MODULES=ON",
                       f"-DUSE_SSE={'ON' if platform.machine().lower() in ('x86_64', 'amd64') else 'OFF'}", "-DUSE_AVX2=OFF", "-DUSE_AVX512=OFF",
                       "-DUSE_VNNI=OFF", "-DUSE_BMI2=OFF"]
            subprocess.run(command, check=True, capture_output=True, timeout=120)
            subprocess.run([cmake, "--build", str(target.parent), "-j", "2"],
                           check=True, capture_output=True, timeout=420)
        except Exception as error:
            raise EngineError("Rapfi 준비에 실패했습니다. g++, make와 네트워크를 확인해 주세요.") from error
    return str(target)


def analyze(moves, milliseconds=600):
    path = ensure_engine()
    board = board_at(moves)
    side = 1 + len(moves) % 2
    commands = ["START 15", "INFO RULE 4", "INFO THREAD_NUM 1", "INFO HASH_SIZE 16384",
                f"INFO TIMEOUT_TURN {milliseconds}", "INFO SHOW_DETAIL 2", "BOARD"]
    commands += [f"{x},{y},{1 if (i%2+1)==side else 2}" for i, (x, y) in enumerate(moves)]
    commands.append("DONE")
    # END는 탐색을 중단시킬 수 있으므로 결과 좌표를 수신한 뒤에만 보낸다.
    import queue
    queue_out = queue.Queue()
    with LOCK:
        process = subprocess.Popen([path], cwd=str(Path(path).parent), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        def read_output():
            for line in process.stdout:
                queue_out.put(line.strip())
            queue_out.put(None)
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        info = {}
        try:
            process.stdin.write("\n".join(commands) + "\n")
            process.stdin.flush()
            while True:
                line = queue_out.get(timeout=15 + milliseconds/1000)
                if line is None:
                    raise EngineError("Rapfi가 결과를 반환하지 않았습니다.")
                if line.startswith("INFO "):
                    parts = line.split(" ", 2)
                    if len(parts) == 3:
                        info[parts[1]] = parts[2]
                if re.fullmatch(r"\d+,\d+", line):
                    move = tuple(map(int, line.split(",")))
                    validate(board, *move, side)
                    break
        except (queue.Empty, OSError, ValueError) as error:
            raise EngineError("엔진 응답이 없거나 합법 수가 아닙니다. 다시 시도해 주세요.") from error
        finally:
            try:
                process.stdin.write("END\n")
                process.stdin.flush()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait()
            reader.join(timeout=2)
            process.stdin.close()
            process.stdout.close()
    rate = float(info["WINRATE"]) if "WINRATE" in info else None
    own_wins = winning_moves(board, side)
    enemy_wins = winning_moves(board, 3-side)
    if own_wins:
        rate = 1.0  # 한 수 즉시 승리는 규칙으로 확인된 결과다.
    elif not moves:
        rate = 0.5  # 무오프닝 초기 국면의 중립 표시. 학습·통계 기반 확률은 아니다.
    legal = [p for p in candidates(board) if not forbidden(board, *p, side)]
    # 추가 표시는 탐색 순위가 아닌 형태 후보이며, 첫 번째만 Rapfi 최선 수다.
    extras = sorted((p for p in legal if p != move),
                    key=lambda p: (p not in own_wins, p not in enemy_wins, abs(p[0]-7)+abs(p[1]-7)))[:2]
    guides = [{"point": p, "label": coord(*p), "kind": "defense" if p in enemy_wins else "attack",
               "source": "Rapfi 최선" if i == 0 else "형태 참고 (미탐색)"}
              for i, p in enumerate([move] + extras)]
    return {"engine": "Rapfi / 내장 classical 평가", "revision": REVISION, "best_move": move,
            "black_winrate": (rate if side == 1 else 1-rate) if rate is not None else None,
            "depth": int(info.get("DEPTH", 0)), "evaluation": info.get("EVAL"),
            "principal_variation": info.get("BESTLINE", ""), "guides": guides,
            "winning_moves": own_wins, "opponent_winning_moves": enemy_wins,
            "estimate": True, "side_to_move": side,
            "rate_note": "초기 국면 중립값" if not moves else "즉시 승리 확인" if own_wins else "Rapfi WINRATE"}
