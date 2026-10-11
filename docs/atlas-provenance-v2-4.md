# Atlas v2.4: expanded NOAA source-product audit (untrusted research handoff)

A new local, noncommercial, spreadsheet-first Human Knowledge Atlas v2.4 release extends the **NOAA-vs-NOAA** month-by-month audit to **59 months**, January 2018 through November 2022, using the official NOAA web-visible Mauna Loa trends table and an inherited manually transcribed NOAA in-situ series. Results:

- 59 paired NOAA monthly product values; **23** exact matches at displayed precision.
- Mean in-situ minus trends **−0.0001695 ppm**; MAE **0.0157627 ppm**; RMSE **0.0264575 ppm**; maximum absolute difference **0.10 ppm**.
- 13 local validator/adversarial tests pass; Excel dashboard and annual summaries are formula-driven with zero detected formula errors.
- **No** original complete NOAA or Scripps source file was downloaded/authenticated by SHA-256. **Zero** independent NOAA–Scripps pairs were computed and **zero** findings were promoted.
- The full release is in a separate Atlas ZIP, with linked CSV/Excel and the preserved prior v2.3 archive. No media included.

Critical provenance improvement in the local release: a hash of a locally supplied data file is now explicitly tagged as *byte integrity only*, **not proof of HTTPS download from the claimed institutional URL**. The offline importer also blocks cross-institution redirects and refuses silent overwrites.

Sources:
- NOAA official trends table: https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt
- NOAA methods: https://gml.noaa.gov/ccgg/about/co2_measurements.html
- Scripps primary record: https://scrippsco2.ucsd.edu/data/primary-mauna-loa-co2-record/

For SGK: a Lean theorem or formal inequality must still be rechecked by the pinned kernel. For CACE: only a genuine solver certificate qualifies as numerical proof. For Expert Robot: the same no-authority-increase, independent audit, sandbox and comparison gates remain mandatory. **This note is not a qualified project run and must not promote any claim.**

**Next gate:** retrieve the full original primary NOAA and Scripps files under approved free compute, record acquisition metadata/hash, align actual monthly observation selection/calibration, and independently compute cross-program statistics.