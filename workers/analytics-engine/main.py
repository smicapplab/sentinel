import sys
from src.nbi_engine import run_nbi_analysis
from src.fraud_radar import run_fraud_radar

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py [nbi|fraud|all] <franchise_id>")
        sys.exit(1)

    command = sys.argv[1]
    franchise_id = sys.argv[2] if len(sys.argv) > 2 else "00000000-0000-0000-0000-000000000001"

    if command in ("nbi", "all"):
        run_nbi_analysis(franchise_id)
        
    if command in ("fraud", "all"):
        run_fraud_radar(franchise_id)

if __name__ == "__main__":
    main()
