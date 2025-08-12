import subprocess
import argparse
import os
import glob

# --------------------
# Tool configurations
# --------------------
APKTOOL = "java -jar apktool_2.12.0.jar"
UBER_APK_SIGNER = "uber-apk-signer.jar"
BUNDLETOOL = "bundletool-all-1.18.1.jar"

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

def pull_apks(package, workdir=None):
    # If workdir not provided, default to package name
    if not workdir or workdir == "workdir":
        workdir = package
    os.makedirs(workdir, exist_ok=True)

    # Get all APK paths for the package
    result = subprocess.run(["adb", "shell", "pm", "path", package],
                            capture_output=True, text=True)
    paths = [p.replace("package:", "").strip() for p in result.stdout.splitlines()]
    if not paths:
        print(f"No APKs found for package: {package}")
        return

    print(f"Found {len(paths)} APK(s) for {package}:")
    for path in paths:
        print(" -", path)

    # Pull each APK into the workdir
    for i, path in enumerate(paths):
        fname = os.path.basename(path)
        local_name = fname
        if os.path.exists(os.path.join(workdir, local_name)):
            local_name = f"split_{i}_{fname}"
        run(["adb", "pull", path, os.path.join(workdir, local_name)])

def decompile_single_apk(apk_path):
    """Decompile a single APK file"""
    if not os.path.exists(apk_path):
        print(f"Error: APK file '{apk_path}' does not exist")
        return
    
    if not apk_path.endswith('.apk'):
        print(f"Error: '{apk_path}' is not an APK file")
        return
    
    outdir = os.path.splitext(apk_path)[0]
    print(f"Decompiling {apk_path} to {outdir}")
    
    try:
        run(APKTOOL.split() + ["d", apk_path, "-o", outdir, "-f"])
        print(f"Successfully decompiled: {apk_path}")
    except RuntimeError as e:
        print(f"Failed to decompile {apk_path}: {e}")

def decompile_apks(workdir):
    # Check if workdir exists
    if not os.path.exists(workdir):
        print(f"Error: Directory '{workdir}' does not exist")
        return
    
    # Find APK files in the workdir
    apk_files = glob.glob(os.path.join(workdir, "*.apk"))
    
    if not apk_files:
        print(f"No APK files found in directory: {workdir}")
        return
    
    print(f"Found {len(apk_files)} APK file(s) to decompile:")
    for apk in apk_files:
        print(f" - {apk}")
    
    # Decompile each APK
    for apk in apk_files:
        outdir = os.path.splitext(apk)[0]
        print(f"Decompiling {apk} to {outdir}")
        try:
            run(APKTOOL.split() + ["d", apk, "-o", outdir, "-f"])
            print(f"Successfully decompiled: {apk}")
        except RuntimeError as e:
            print(f"Failed to decompile {apk}: {e}")

def build_and_sign(workdir):
    if not os.path.exists(workdir):
        print(f"Error: Directory '{workdir}' does not exist")
        return
        
    folders_to_build = []
    for folder in os.listdir(workdir):
        full_path = os.path.join(workdir, folder)
        if os.path.isdir(full_path) and not folder.endswith(".apk"):
            folders_to_build.append(folder)
    
    if not folders_to_build:
        print(f"No decompiled APK folders found in: {workdir}")
        return
    
    print(f"Found {len(folders_to_build)} folder(s) to build:")
    for folder in folders_to_build:
        print(f" - {folder}")
    
    for folder in folders_to_build:
        full_path = os.path.join(workdir, folder)
        apk_out = os.path.join(workdir, f"{folder}-unsigned.apk")
        try:
            run(APKTOOL.split() + ["b", full_path, "-o", apk_out])
            run(["java", "-jar", UBER_APK_SIGNER, "-a", apk_out])
            print(f"Successfully built and signed: {folder}")
        except RuntimeError as e:
            print(f"Failed to build/sign {folder}: {e}")

def install_split_apks(workdir):
    if not os.path.exists(workdir):
        print(f"Error: Directory '{workdir}' does not exist")
        return
        
    apks = sorted(glob.glob(os.path.join(workdir, "*-aligned-debugSigned.apk")))
    if not apks:
        print("No signed APKs found.")
        return
    
    print(f"Installing {len(apks)} APK(s):")
    for apk in apks:
        print(f" - {apk}")
    
    run(["adb", "install-multiple", "-r"] + apks)

def build_universal(workdir, output_apk):
    """Create universal APK from AAB file (requires AAB file in workdir)"""
    if not os.path.exists(workdir):
        print(f"Error: Directory '{workdir}' does not exist")
        return
    
    # Look for AAB file in workdir
    aab_files = glob.glob(os.path.join(workdir, "*.aab"))
    if not aab_files:
        print("No AAB files found. Universal build requires an Android App Bundle (.aab) file.")
        return
    
    aab_file = aab_files[0]  # Use first AAB found
    print(f"Creating universal APK from: {aab_file}")
    
    try:
        run(["java", "-jar", BUNDLETOOL, "build-apks",
             "--mode=universal",
             "--bundle", aab_file,
             "--output", output_apk])
        print(f"Successfully created universal APK: {output_apk}")
    except RuntimeError as e:
        print(f"Failed to create universal APK: {e}")
        print("Note: This feature is mainly for converting AAB files to installable APKs")

# --------------------
# CLI
# --------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["list", "pull", "decompile", "build", "install", "universal"])
    parser.add_argument("search_or_package", nargs="?", help="Search term for list, package name for pull, OR directory/file path for decompile")
    parser.add_argument("--dir", default="workdir", help="Working directory")
    args = parser.parse_args()

    if args.mode == "list":
        list_packages(args.search_or_package)
    elif args.mode == "pull":
        # Use custom directory if specified, otherwise use package name
        if args.dir != "workdir":
            target_dir = args.dir
        else:
            target_dir = args.search_or_package
            
        if not args.search_or_package:
            print("Error: package name required for pull command")
        else:
            pull_apks(args.search_or_package, target_dir)
    elif args.mode == "decompile":
        # Use the provided path if given, otherwise use --dir
        target_dir = args.search_or_package if args.search_or_package else args.dir
        
        # If it's a single APK file, decompile just that file
        if target_dir.endswith('.apk') and os.path.isfile(target_dir):
            decompile_single_apk(target_dir)
        else:
            # It's a directory, decompile all APKs in it
            decompile_apks(target_dir)
    elif args.mode == "build":
        build_and_sign(args.dir)
    elif args.mode == "install":
        install_split_apks(args.dir)
    elif args.mode == "universal":
        build_universal(args.dir, "universal.apk")