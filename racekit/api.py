from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

def fetch_event(cfg, offline):
    from racekit.client import RaceResultClient
    from racekit.dataset import build_dataset, list_snapshots, snapshot_previous, summarize, write_outputs
    from racekit.normalize import normalize_list

    if not offline:
        snap = snapshot_previous(cfg, keep=cfg.snapshot_keep)
        if snap is not None:
            logger.info("-> önceki veri arşivlendi: %s", snap.relative_to(cfg.data_dir))
        else:
            logger.info("-> arşivlenecek önceki veri bulunamadı (ilk çekim)")

    client = RaceResultClient(cfg, offline=offline)
    raw = client.fetch_all()

    frames = {
        spec.role: normalize_list(raw[spec.role], spec.role, cfg.result_role)
        for spec in cfg.lists
    }

    df = build_dataset(cfg, frames)
    xlsx_path, csv_path = write_outputs(df, cfg)

    summarize(df, cfg)
    logger.info("\nYazılan dosyalar:\n   %s\n   %s", xlsx_path, csv_path)
    snaps = list_snapshots(cfg)
    if snaps:
        logger.info("Arşiv (geri dönülebilir önceki sürümler): %d kayıt", len(snaps))
        for s in snaps[-3:]:
            logger.info("   %s", s)
    return df, xlsx_path, csv_path