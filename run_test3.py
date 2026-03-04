import subprocess

with open('test3_results_safe.txt', 'w', encoding='utf-8') as f:
    result = subprocess.run(['python', '-u', 'test_reservoir_v3.py'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    f.write(result.stdout)
    f.write(result.stderr)
print("COMPLETED")
