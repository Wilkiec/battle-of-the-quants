# Local data files

Source datasets are not redistributed in this repository. Add the files below locally after obtaining them from authorized sources; the `.gitignore` keeps them out of commits.

- `cattle_beef_cold_storage_monthly.csv` - monthly USDA beef cold-storage series used for the signal.
- `botq_monthly_stock_returns.csv.gz` - monthly panel derived from the BotQ competition export. Use only if your competition access terms allow it.
- `target_stocks_yahoo_monthly_returns.csv` - dividend-adjusted monthly returns for TSN, CPB, and GIS used for the December 2025 extension.

To build the BotQ panel from an authorized daily export, see `scripts/prepare_botq_monthly_returns.py`.
