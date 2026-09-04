import sys
from src.nbi_engine import run_nbi_analysis
from src.fraud_radar import run_fraud_radar
from src.whitespace_radar import run_whitespace_radar

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py [nbi|fraud|whitespace|all] <target_id>")
        sys.exit(1)

    command = sys.argv[1]
    target_id = sys.argv[2] if len(sys.argv) > 2 else "00000000-0000-0000-0000-000000000001"

    if command in ("nbi", "all"):
        run_nbi_analysis(target_id)
        
    if command in ("fraud", "all"):
        run_fraud_radar(target_id)

    if command in ("whitespace", "all"):
        # companyId defaults to comp-1 (Pizza Hut)
        company_id = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith("comp-") else "comp-1"
        run_whitespace_radar(company_id=company_id)

if __name__ == "__main__":
    main()
