from __future__ import annotations

from fovux.core.paths import ensure_fovux_dirs
from fovux.core.runs import RunRegistry
from fovux.schemas.management import RunCompareInput
from fovux.tools.run_compare import _run_run_compare


def test_run_compare_experiment_advisor(tmp_path, monkeypatch):
    """Test run_compare with multiple runs to check Pareto, config diffs, and advisor."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    paths = ensure_fovux_dirs(tmp_path)
    registry = RunRegistry(paths.runs_db)

    # 1. Create run_fast (YOLO11n, low latency/size, low mAP)
    # Pareto optimal because of lowest latency/size.
    run_fast_dir = paths.runs / "run_fast"
    run_fast_dir.mkdir(parents=True)
    (run_fast_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B),metrics/precision(B),metrics/recall(B)\n"
        "0,0.50,0.52,0.48\n"
        "1,0.58,0.60,0.55\n",
        encoding="utf-8",
    )
    # write args.yaml for config diff
    (run_fast_dir / "args.yaml").write_text("epochs: 10\nbatch: 16\n", encoding="utf-8")
    registry.create_run(
        run_id="run_fast",
        run_path=run_fast_dir,
        model="yolov8n.pt",
        dataset_path=tmp_path,
        task="detect",
        epochs=10,
    )

    # 2. Create run_mid (YOLO11m, med latency/size, med mAP)
    # Pareto optimal: better accuracy than fast, better latency than large.
    run_mid_dir = paths.runs / "run_mid"
    run_mid_dir.mkdir(parents=True)
    (run_mid_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B),metrics/precision(B),metrics/recall(B)\n"
        "0,0.68,0.70,0.65\n"
        "1,0.72,0.74,0.70\n",
        encoding="utf-8",
    )
    (run_mid_dir / "args.yaml").write_text("epochs: 20\nbatch: 32\n", encoding="utf-8")
    registry.create_run(
        run_id="run_mid",
        run_path=run_mid_dir,
        model="yolov8m.pt",
        dataset_path=tmp_path,
        task="detect",
        epochs=20,
    )

    # 3. Create run_large (YOLO11x, high latency/size, high mAP)
    # Pareto optimal because of highest accuracy.
    run_large_dir = paths.runs / "run_large"
    run_large_dir.mkdir(parents=True)
    (run_large_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B),metrics/precision(B),metrics/recall(B)\n"
        "0,0.80,0.82,0.78\n"
        "1,0.85,0.88,0.83\n",
        encoding="utf-8",
    )
    (run_large_dir / "args.yaml").write_text("epochs: 30\nbatch: 32\n", encoding="utf-8")
    registry.create_run(
        run_id="run_large",
        run_path=run_large_dir,
        model="yolov8x.pt",
        dataset_path=tmp_path,
        task="detect",
        epochs=30,
    )

    # 4. Create run_dominated (Strictly dominated by run_mid on all dimensions)
    # Not Pareto optimal: run_mid has better mAP (0.72 vs 0.65), size (40.8 vs 85.3),
    # and latency (13.9 vs 21.4).
    run_dominated_dir = paths.runs / "run_dominated"
    run_dominated_dir.mkdir(parents=True)
    (run_dominated_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B),metrics/precision(B),metrics/recall(B)\n"
        "0,0.60,0.62,0.58\n"
        "1,0.65,0.66,0.62\n",
        encoding="utf-8",
    )
    (run_dominated_dir / "args.yaml").write_text("epochs: 20\nbatch: 32\n", encoding="utf-8")
    registry.create_run(
        run_id="run_dominated",
        run_path=run_dominated_dir,
        model="yolov8l.pt",
        dataset_path=tmp_path,
        task="detect",
        epochs=20,
    )

    # Run the comparison
    inp = RunCompareInput(run_ids=["run_fast", "run_mid", "run_large", "run_dominated"])
    output = _run_run_compare(inp)

    # Verify Leaderboard Sorting (Sorted by mAP descending)
    expected_order = ["run_large", "run_mid", "run_dominated", "run_fast"]
    actual_order = [run.run_id for run in output.compared_runs]
    assert actual_order == expected_order
    assert output.best_run_id == "run_large"

    # Verify Pareto Frontier calculations
    # Dominant runs: run_fast, run_mid, run_large. Dominated run: run_dominated.
    assert "run_fast" in output.pareto_frontier_run_ids
    assert "run_mid" in output.pareto_frontier_run_ids
    assert "run_large" in output.pareto_frontier_run_ids
    assert "run_dominated" not in output.pareto_frontier_run_ids

    # Find run summaries to verify individual pareto optimal flags
    summaries = {r.run_id: r for r in output.compared_runs}
    assert summaries["run_fast"].pareto_optimal is True
    assert summaries["run_mid"].pareto_optimal is True
    assert summaries["run_large"].pareto_optimal is True
    assert summaries["run_dominated"].pareto_optimal is False

    # Verify Config Diffs
    # "epochs" should differ (10 vs 20 vs 30 vs 20)
    # "batch" should differ (16 vs 32 vs 32 vs 32)
    assert "epochs" in output.config_diffs
    assert "batch" in output.config_diffs
    assert output.config_diffs["epochs"]["run_fast"] == 10
    assert output.config_diffs["epochs"]["run_large"] == 30
    assert output.config_diffs["batch"]["run_fast"] == 16
    assert output.config_diffs["batch"]["run_mid"] == 32

    # Verify Model Card markdown generation exists for each run
    for run_id in ["run_fast", "run_mid", "run_large", "run_dominated"]:
        assert run_id in output.model_cards
        card = output.model_cards[run_id]
        assert f"Model Card: {run_id}" in card
        assert f"Architecture:** {summaries[run_id].model}" in card

    # Verify Experiment Advisor outputs normal accuracy-solid recommendation
    # since best run (run_large) has mAP50 = 0.85 (>0.6) and balanced precision/recall.
    assert "accuracy is solid" in output.suggested_next_experiment
    assert "quantization" in output.suggested_next_experiment.lower()


def test_run_compare_advisor_imbalances(tmp_path, monkeypatch):
    """Test Experiment Advisor recommendations for low mAP and precision/recall imbalances."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    paths = ensure_fovux_dirs(tmp_path)
    registry = RunRegistry(paths.runs_db)

    # Case 1: Low mAP50 (under 0.6)
    low_dir = paths.runs / "run_low"
    low_dir.mkdir(parents=True)
    (low_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B),metrics/precision(B),metrics/recall(B)\n0,0.45,0.50,0.40\n",
        encoding="utf-8",
    )
    registry.create_run(
        run_id="run_low",
        run_path=low_dir,
        model="yolov8n.pt",
        dataset_path=tmp_path,
        task="detect",
        epochs=1,
    )

    out_low = _run_run_compare(RunCompareInput(run_ids=["run_low"]))
    assert "low mAP50" in out_low.suggested_next_experiment
    assert "larger model capacity" in out_low.suggested_next_experiment

    # Case 2: Precision much higher than Recall (> 0.12 diff)
    high_prec_dir = paths.runs / "run_high_prec"
    high_prec_dir.mkdir(parents=True)
    (high_prec_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B),metrics/precision(B),metrics/recall(B)\n0,0.65,0.85,0.60\n",
        encoding="utf-8",
    )
    registry.create_run(
        run_id="run_high_prec",
        run_path=high_prec_dir,
        model="yolov8n.pt",
        dataset_path=tmp_path,
        task="detect",
        epochs=1,
    )

    out_prec = _run_run_compare(RunCompareInput(run_ids=["run_high_prec"]))
    assert "low recall" in out_prec.suggested_next_experiment
    assert "data augmentations" in out_prec.suggested_next_experiment

    # Case 3: Recall much higher than Precision (> 0.12 diff)
    high_rec_dir = paths.runs / "run_high_rec"
    high_rec_dir.mkdir(parents=True)
    (high_rec_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B),metrics/precision(B),metrics/recall(B)\n0,0.65,0.60,0.80\n",
        encoding="utf-8",
    )
    registry.create_run(
        run_id="run_high_rec",
        run_path=high_rec_dir,
        model="yolov8n.pt",
        dataset_path=tmp_path,
        task="detect",
        epochs=1,
    )

    out_rec = _run_run_compare(RunCompareInput(run_ids=["run_high_rec"]))
    assert "low precision" in out_rec.suggested_next_experiment
    assert "background noise" in out_rec.suggested_next_experiment
