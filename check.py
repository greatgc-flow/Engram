import os
import subprocess
import glob
import re

tests_dir = "_sys/tests/unit"
test_files = [f for f in os.listdir(tests_dir) if f.startswith("test_") and f.endswith(".py")]

for test_file in test_files:
    # clear existing
    for f in os.listdir('.'):
        if re.match(r'^[a-z0-9_]{8}$', f) and os.path.isfile(f):
            os.remove(f)
            
    subprocess.run(["python", "-m", "pytest", os.path.join(tests_dir, test_file), "-q"], capture_output=True)
    
    # check new
    found = False
    for f in os.listdir('.'):
        if re.match(r'^[a-z0-9_]{8}$', f) and os.path.isfile(f):
            print(f"Junk created by {test_file}: {f}")
            found = True
            os.remove(f)
    if found:
        print(f"--- {test_file} is the culprit! ---")
