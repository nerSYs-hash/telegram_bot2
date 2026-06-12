import os
import subprocess

def run(cmd, cwd=None):
    print(f"=== Running: {cmd} ===")
    res = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    print("STDOUT:")
    print(res.stdout)
    if res.stderr:
        print("STDERR:")
        print(res.stderr)
    print(f"EXIT CODE: {res.returncode}")
    print("="*40)
    return res.returncode

print("Starting Git Push (SKIPPING BUILD DUE TO NODE.JS CRASH)...")

run("git status", cwd=r"c:\bot_2\telegram_bot2")
run("git add .", cwd=r"c:\bot_2\telegram_bot2")
run("git commit -F commit_msg.txt", cwd=r"c:\bot_2\telegram_bot2")
run("git push", cwd=r"c:\bot_2\telegram_bot2")
print("Done!")
