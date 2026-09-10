import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--artist", required=True)
args = parser.parse_args()

print(f"Refresh requested for {args.artist}")
print("Live source adapters are scaffolded; enable/implement sources in config/sources.yml.")
