"""Spustí celý dátový pipeline jedným príkazom:

    python -m pipeline.run_pipeline              # stiahne dáta a všetko prepočíta
    python -m pipeline.run_pipeline --bez-stahovania   # len prepočíta z už stiahnutých dát

Poradie: sťahovanie (+ manifest) -> spojenie dát -> párovanie CZ–SK -> KIQ2 -> wiki
"""

import sys

from pipeline import kiq2_posun, manifest, match_cz_sk, normalize, sources_cz, sources_sk, wiki


def main(stahovat: bool = True) -> None:
    if stahovat:
        print("1/5 Sťahujem dáta (ČR, SR)…")
        sources_cz.download_all()
        sources_sk.download_all()
    else:
        print("1/5 Sťahovanie preskočené, doplním len manifest…")
        manifest.doplnit_existujuce()

    print("\n2/5 Spájam dáta…")
    normalize.run()

    print("\n3/5 Párujem látky ČR a SR…")
    match_cz_sk.run()

    print("\n4/5 KIQ2 – časový posun…")
    kiq2_posun.run()

    print("\n5/5 Generujem wiki…")
    wiki.run()

    print("\nPipeline hotový.")


if __name__ == "__main__":
    main(stahovat="--bez-stahovania" not in sys.argv)
