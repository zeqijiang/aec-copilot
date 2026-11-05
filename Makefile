.PHONY: install test demo eval web-install web-build

install:
	python -m pip install -e ".[all]"

test:
	pytest

demo:
	aec run "生成一栋30m×20m的两层小楼，层高3.6m，外墙200mm，中间加一道隔墙，四个角放柱子" --output runs

eval:
	python eval/run_eval.py eval/results

web-install:
	cd apps/web && npm ci

web-build:
	cd apps/web && npm run typecheck && npm run build
