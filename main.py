import subprocess
import argparse
import os
import glob

# --------------------
# Utility functions
# --------------------
def run(cmd):
    print(f"[RUN] {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")

# --------------------
# Core commands
# --------------------
def list_packages(search=None):
    result = subprocess.run(["adb", "shell", "pm", "list", "packages"], capture_output=True, text=True)
    packages = [p.replace("package:", "").strip() for p in result.stdout.splitlines()]
    if search:
        packages = [p for p in packages if search.lower() in p.lower()]
    for p in packages:
        print(p)

def pull_apks(package, workdir):
    os.makedirs(workdir, exist_ok=True)
    result = subprocess.run(["adb", "shell", "pm", "path", package], capture_output=True, text=True)
    paths = [p.replace("package:", "").strip() for p in result.stdout.splitlines()]
    for path in paths:
        fname = os.path.basename(path)
        run(["adb", "pull", path, os.path.join(workdir, fname)])

def decompile_apks(workdir):
    for apk in glob.glob(os.path.join(workdir, "*.apk")):
        outdir = os.path.splitext(apk)[0]
        run(["apktool", "d", apk, "-o", outdir, "-f"])

def build_and_sign(workdir):
    for folder in os.listdir(workdir):
        full_path = os.path.join(workdir, folder)
        if os.path.isdir(full_path) and not folder.endswith(".apk"):
            apk_out = os.path.join(workdir, f"{folder}-unsigned.apk")
            run(["apktool", "b", full_path, "-o", apk_out])
            run(["java", "-jar", "uber-apk-signer.jar", "-a", apk_out])

def install_split_apks(workdir):
    apks = sorted(glob.glob(os.path.join(workdir, "*-aligned-debugSigned.apk")))
    if not apks:
        print("No signed APKs found.")
        return
    run(["adb", "install-multiple", "-r"] + apks)

def build_universal(workdir, output_apk):
    apks = sorted(glob.glob(os.path.join(workdir, "*-aligned-debugSigned.apk")))
    if not apks:
        print("No signed APKs found.")
        return
    run(["java", "-jar", "bundletool.jar", "build-apks",
         "--mode=universal",
         "--output", output_apk,
         "--bundle", "base.aab",  # requires converted AAB if needed
         "--ks", "mykey.keystore", "--ks-pass", "pass:password",
         "--ks-key-alias", "alias_name", "--key-pass", "pass:password"])

# --------------------
# CLI
# --------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["list", "pull", "decompile", "build", "install", "universal"])
    parser.add_argument("search_or_package", nargs="?", help="Search term for list OR package name for pull")
    parser.add_argument("--dir", default="workdir", help="Working directory")
    args = parser.parse_args()

    if args.mode == "list":
        list_packages(args.search_or_package)
    elif args.mode == "pull":
        if not args.search_or_package:
            print("Error: package name required")
        else:
            pull_apks(args.search_or_package, args.dir)
    elif args.mode == "decompile":
        decompile_apks(args.dir)
    elif args.mode == "build":
        build_and_sign(args.dir)
    elif args.mode == "install":
        install_split_apks(args.dir)
    elif args.mode == "universal":
        build_universal(args.dir, "universal.apk")
