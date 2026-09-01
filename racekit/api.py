from __future__ import annotations

def fetch_event(cfg, offline):
    from racekit.client import RaceResultClient
    from racekit.dataset import build_dataset, list_snapshots, snapshot_previous, summarize, write_outputs
    from racekit.normalize import normalize_list

    if not offline:
        snap = snapshot_previous(cfg)
        if snap is not None:
            print(f"-> önceki veri arşivlendi: {snap.relative_to(cfg.data_dir)}")
        else:
            print("-> arşivlenecek önceki veri bulunamadı (ilk çekim)")

    client = RaceResultClient(cfg, offline=offline)
    raw = client.fetch_all()

    frames = {
        spec.role: normalize_list(raw[spec.role], spec.role, cfg.result_role)
        for spec in cfg.lists
    }

    df = build_dataset(cfg, frames)
    xlsx_path, csv_path = write_outputs(df, cfg)

    summarize(df, cfg)
    print("\nYazılan dosyalar:")
    print(f"   {xlsx_path}")
    print(f"   {csv_path}")
    snaps = list_snapshots(cfg)
    if snaps:
        print(f"\nArşiv (geri dönülebilir önceki sürümler): {len(snaps)} kayıt")
        for s in snaps[-3:]:
            print(f"   {s}")
    return df, xlsx_path, csv_path