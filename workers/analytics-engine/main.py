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
        # companyId defaults to comp-1 (Pizza Hut), optional lgu_code in arg 3 or arg 2
        company_id = "comp-1"
        lgu_code = None
        if len(sys.argv) > 2:
            if sys.argv[2].startswith("comp-"):
                company_id = sys.argv[2]
                if len(sys.argv) > 3:
                    lgu_code = sys.argv[3]
            else:
                lgu_code = sys.argv[2]
        run_whitespace_radar(company_id=company_id, lgu_code=lgu_code)

if __name__ == "__main__":
    main()
