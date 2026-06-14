# SD Hotspot-Emergence — Milestone 1 + 2 targets
# (Windows: use `make` via Git Bash / WSL, or run the underlying python -m commands directly.)

.PHONY: data baseline features features_infra model model_ablation model_terrain_supp model_frozen eval2 eval3a eval3b eval4 audit test clean export_sample export_real names export_panel export_verified dashboard_dev dashboard_build

data:           ## Ingest -> node spine -> candidate panel + labels
	python -m src.ingest.run
	python -m src.gis.build_spine
	python -m src.labels.build_panel

baseline:       ## Frequency baseline + metrics (random vs spatial-block) with bootstrap CIs
	python -m src.eval.baseline

audit:          ## Leakage audit (fails non-zero on violation; includes A9 infra vintage)
	python -m src.audit.leakage

test:           ## Unit tests + leakage audit
	pytest -q
	python -m src.audit.leakage

features:       ## Build crash + emergence feature table (+ feature_dictionary.csv)
	python -m src.features.build_crash_emergence

features_infra: ## M3b: download OSM history/GTFS/DEM + build infra feature groups 3-7
	python -m src.features.build_infra_features

model:          ## Fit baseline + logistic + XGBoost-binary + XGBoost-Tweedie (crash-only)
	python -m src.model.fit

model_ablation: ## M3b: incremental ablation across feature groups (crash-only → all)
	python -m src.model.fit_ablation

model_terrain_supp: ## M3b: supplemental terrain step (re-runs with fixed slope_pct)
	python -m src.model.fit_terrain_supp

model_frozen:   ## M4 Protocol A: fit 4 feature sets with frozen M3a hyperparameters (no Optuna)
	python -m src.model.fit_frozen

eval2:          ## M2 metrics table (count + ranked) + buffer diagnostic
	python -m src.eval.milestone2

eval3a:         ## M3a clean-data signal re-validation (gate before features)
	python -m src.eval.milestone3a

eval3b:         ## M3b incremental ablation evaluation + report
	python -m src.eval.milestone3b

eval4:          ## M4 Protocol A eval + recall@K + decision memo (requires model_frozen)
	python -m src.eval.milestone4

clean:          ## Remove processed + model intermediates (keeps raw snapshots)
	python -c "import shutil,glob,os; [shutil.rmtree(p,ignore_errors=True) for p in ['data/proc','data/model']]"

export_sample:  ## Generate sample data for dashboard development
	python scripts/generate_sample_data.py

names:          ## Build intersection name labels from OSMnx graph
	python scripts/build_intersection_names.py

export_panel:   ## Assemble enriched export panel (requires model_frozen + eval4 + names)
	python scripts/build_export_panel.py

export_real:    ## Export real model predictions to dashboard data files
	python scripts/build_export_panel.py

export_verified: ## Export verified run (2016-2021 -> 2022-2024) to dashboard
	python scripts/build_export_panel_verified.py

dashboard_dev:  ## Start dashboard development server (requires npm install first)
	cd dashboard && npm run dev

dashboard_build: ## Build dashboard for production deployment
	cd dashboard && npm run build
