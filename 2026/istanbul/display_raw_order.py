import csv
from collections import defaultdict, OrderedDict

CSV_PATH = "raceresult_data/bogazici_38_dataset.csv"

with open(CSV_PATH, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

finished = [r for r in rows if r["status"] == "FINISHED"]
males = sorted([r for r in finished if r["gender"] == "M"], key=lambda r: int(r["swim_seconds"]))

user = next(r for r in males if r["bib"] == "1831")
user_idx = males.index(user)
current_rank = user_idx + 1

bytime = defaultdict(list)
for r in males:
    bytime[r["time_text"]].append(r)

prev = males[:user_idx]

tied_prev = [r for r in prev if len(bytime[r["time_text"]]) > 1]

distinct_prev = set(r["time_text"] for r in prev)

extra_prev = sum(max(0, len(bytime[t]) - 1) for t in distinct_prev)

tie_groups = OrderedDict()
for r in prev:
    t = r["time_text"]
    if len(bytime[t]) > 1 and t not in tie_groups:
        tie_groups[t] = [g["bib"] for g in bytime[t]]

print("=" * 70)
print("KULLANICI : %s %s | bib %s | süre %s" % (user["first_name"], user["last_name"], user["bib"], user["time_text"]))
print("MEVCUT SIRA (erkekler): %s" % user["gender_rank"])
print("Önünde bitiren erkek sayısı:", len(prev))
print("Erkeklerde toplam bitiren:", len(males), "| Kadınlarda:", len(finished) - len(males))
print("=" * 70)

print("\n1:11:31 örneği (verideki gerçek sıralar):")
for bib in ("855", "2369"):
    r = next(x for x in males if x["bib"] == bib)
    print("  bib %s %-18s %s | sıra %s | grup %d kişi | (comp. sıra %s)" % (
        r["bib"], r["last_name"], r["time_text"], r["gender_rank"],
        len(bytime[r["time_text"]]), r["gender_rank_computed"]))

print("\nÖnünüzdeki aynı-süre (tie) grupları: %d grup, %d kişi, fazlalık %d kişi" % (
    len(tie_groups), sum(len(v) for v in tie_groups.values()), extra_prev))
for t, bibs in tie_groups.items():
    print("   %s: %d kişi -> bib %s" % (t, len(bibs), bibs))

print("\n" + "=" * 70)
print("SENARYO SONUÇLARI (erkekler):")
print("-" * 70)
print("1) Önünüzdeki aynı süreye sahip yarışmacıların TAMAMI yarıştan çıksaydı:")
print("   çıkan kişi: %d  ->  yeni sıra: %d - %d = %d" % (
    len(tied_prev), current_rank, len(tied_prev), current_rank - len(tied_prev)))
print()
print("2) Her aynı-süre grubundan yalnızca 1 kişi kalsaydı (fazlalıklar çıksaydı):")
print("   çıkan kişi: %d  ->  yeni sıra: %d - %d = %d" % (
    extra_prev, current_rank, extra_prev, current_rank - extra_prev))
print("   (= 'aynı süre tek derece' sayılan yoğun/dense sıralama: %d)" % (
    len(distinct_prev) + 1))
print()
print("3) Aynı süre = aynı sıra (yarışma/competition sıralaması) kullanılsaydı:")
print("   kullanıcı 1:11:40 grubunun ilk üyesi olduğu için sırası yine %d olurdu;" % (len(prev) + 1))
print("   sadece arkasındaki aynı süreli yarışmacı da %d.'yi paylaşırdı." % (len(prev) + 1))
print("=" * 70)