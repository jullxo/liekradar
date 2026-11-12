"""Spustí celý dátový pipeline: python -m pipeline.run_pipeline"""

from pipeline import match_cz_sk, normalize, risk_score, sources_cz, sources_eu, sources_sk


def main() -> None:
    print("1/4 Sťahujem dáta…")
    sources_cz.download_all()
    sources_sk.download_all()
    sources_eu.download_all()

    print("2/4 Čistím a zjednocujem…")
    normalize.run()

    print("3/4 Párujem lieky CZ <-> SK…")
    match_cz_sk.run()

    print("4/4 Počítam skóre rizika…")
    risk_score.run()

    print("Hotovo.")


if __name__ == "__main__":
    main()
