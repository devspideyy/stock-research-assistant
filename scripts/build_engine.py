"""Build the native engine with CMake, or a portable GCC/Clang compiler.

Run this with the project's Python environment. Compiler downloads are never implicit.
"""

from __future__ import annotations

import os
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_compiler() -> str | None:
    explicit = os.getenv("CXX")
    if explicit and (Path(explicit).is_file() or shutil.which(explicit)):
        return explicit
    for command in ("clang++", "g++", "c++"):
        if found := shutil.which(command):
            return found
    for pattern in ("**/bin/clang++.exe", "**/bin/g++.exe"):
        candidates = sorted((ROOT / ".tools").glob(pattern))
        if candidates:
            return str(candidates[0])
    return None


def build() -> Path:
    compiler = find_compiler()
    cmake = shutil.which("cmake")
    build_dir = ROOT / "engine/build"
    build_dir.mkdir(parents=True, exist_ok=True)
    executable = build_dir / ("engine_cli.exe" if os.name == "nt" else "engine_cli")
    environment = os.environ.copy()
    if compiler:
        environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
    if cmake and (not compiler or os.name != "nt" or shutil.which("ninja")):
        configure = [
            cmake,
            "-S",
            str(ROOT / "engine"),
            "-B",
            str(build_dir),
            "-DCMAKE_BUILD_TYPE=Release",
        ]
        if compiler:
            configure.append(f"-DCMAKE_CXX_COMPILER={compiler}")
        if shutil.which("ninja"):
            configure += ["-G", "Ninja"]
        subprocess.run(configure, check=True, env=environment)
        subprocess.run(
            [cmake, "--build", str(build_dir), "--config", "Release"], check=True, env=environment
        )
    elif compiler:
        sources = sorted((ROOT / "engine/src").rglob("*.cpp"))
        if not sources:
            raise RuntimeError("No C++ engine sources were found.")
        command = [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-I",
            str(ROOT / "engine/include"),
            "-I",
            str(ROOT / "engine/third_party"),
        ]
        if os.name == "nt":
            command.append("-static")
        command += [str(source) for source in sources] + ["-o", str(executable)]
        subprocess.run(command, check=True, cwd=ROOT, env=environment)
    else:
        raise RuntimeError(
            "Install a C++17 compiler (MSVC with CMake, or GCC/Clang), then retry. "
            "CXX may point to a compiler. No toolchain was downloaded by this script."
        )
    if not executable.exists():
        release = build_dir / "Release" / executable.name
        if release.exists():
            return release
        raise RuntimeError("Build finished but engine_cli was not found.")
    return executable


def test_native() -> None:
    """Compile and run the native unit executable without requiring CMake."""
    compiler = find_compiler()
    if not compiler:
        raise RuntimeError("A GCC/Clang compiler is required for this direct native-test command.")
    executable = ROOT / "engine/build" / ("engine_tests.exe" if os.name == "nt" else "engine_tests")
    command = [
        compiler,
        "-std=c++17",
        "-O2",
        "-I",
        str(ROOT / "engine/include"),
        "-I",
        str(ROOT / "engine/third_party"),
        str(ROOT / "engine/src/engine.cpp"),
        str(ROOT / "engine/tests/test_engine.cpp"),
        "-o",
        str(executable),
    ]
    if os.name == "nt":
        command.insert(1, "-static")
    subprocess.run(command, check=True, cwd=ROOT)
    subprocess.run([str(executable)], check=True, cwd=ROOT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Also compile and run C++ unit tests.")
    args = parser.parse_args()
    try:
        print(f"Native engine ready: {build()}")
        if args.test:
            test_native()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)
