"""Iterative visualization refinement mechanism for FinSight."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go

from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.gemini_client import GeminiClient


@dataclass
class VisualizationIteration:
    iteration: int
    spec: Dict[str, Any]
    figure_json: str
    figure_png_b64: str
    feedback: str


class IterativeVisualizer:
    """Generates charts and refines them based on Gemini feedback."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        gemini_client: GeminiClient,
        max_iterations: int = 3,
    ) -> None:
        self.orchestrator = orchestrator
        self.gemini = gemini_client
        self.max_iterations = max_iterations

    def run(
        self,
        dataframe_uid: str,
        spec: Dict[str, Any],
        goal: str,
    ) -> Dict[str, Any]:
        variable = self.orchestrator.variable_space.get(dataframe_uid)
        df_payload = variable.value
        dataframe = df_payload.get("dataframe") if isinstance(df_payload, dict) else None

        if dataframe is None:
            raise ValueError("Expected dataframe payload stored in variable space.")

        iterations: List[VisualizationIteration] = []
        current_spec = spec.copy()

        for iteration in range(1, self.max_iterations + 1):
            figure_json, figure_png_b64 = self._render_figure(dataframe, current_spec)
            feedback = self._request_feedback(goal, current_spec, figure_json, figure_png_b64, iteration)

            iterations.append(
                VisualizationIteration(
                    iteration=iteration,
                    spec=current_spec.copy(),
                    figure_json=figure_json,
                    figure_png_b64=figure_png_b64,
                    feedback=feedback,
                )
            )

            if "APPROVED" in feedback.upper():
                break
            current_spec = self._apply_feedback(current_spec, feedback)

        result_uid = self.orchestrator.register_data(
            name=f"visualization_{variable.metadata.name}",
            value={
                "dataframe_uid": dataframe_uid,
                "iterations": [
                    {
                        "iteration": item.iteration,
                        "spec": item.spec,
                        "figure_json": item.figure_json,
                        "figure_png_b64": item.figure_png_b64,
                        "feedback": item.feedback,
                    }
                    for item in iterations
                ],
                "final_spec": current_spec,
            },
            description=f"Visualization refinements for {variable.metadata.name}",
            tags=["visualization", "chart"],
            source="iterative_visualizer",
        )

        return {"visualization_uid": result_uid, "iterations": len(iterations)}

    def _render_figure(self, dataframe, spec: Dict[str, Any]) -> tuple[str, str]:
        chart_type = spec.get("type", "line")
        x_col = spec.get("x")
        y_cols = spec.get("y", [])
        title = spec.get("title", "Generated Chart")

        df = dataframe.copy()
        if isinstance(df, dict):
            df = pd.DataFrame(df)
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)

        df = df.sort_index()

        if isinstance(df.columns, pd.MultiIndex):
            flattened = []
            for column in df.columns:
                labels = [str(level) for level in column if level and str(level).lower() != "nan"]
                flattened.append("_".join(labels) if labels else str(column))
            df.columns = flattened

        def _resolve_series(target: str) -> Optional[pd.Series]:
            if target in df.columns:
                return df[target]
            for column in df.columns:
                if str(column).lower() == target.lower():
                    return df[column]
            for column in df.columns:
                if target.lower() in str(column).lower():
                    return df[column]
            return None

        # Ensure sensible defaults
        if not y_cols:
            candidate = _resolve_series("Close")
            if candidate is not None:
                y_cols = ["Close"]
            elif df.columns.any():
                y_cols = [str(df.columns[0])]

        if x_col and x_col in df.columns:
            x_series = df[x_col]
        else:
            x_series = pd.Series(df.index, index=df.index)

        if not pd.api.types.is_datetime64_any_dtype(x_series):
            with pd.option_context("mode.use_inf_as_na", True):
                try:
                    x_series = pd.to_datetime(x_series, errors="coerce")
                except (TypeError, ValueError):
                    pass

        fig = go.Figure()
        traces_added = 0

        for col in y_cols:
            series = _resolve_series(col)
            if series is None:
                continue
            frame = pd.DataFrame({"x": x_series, "y": series}).dropna()
            if frame.empty:
                continue
            if chart_type == "line":
                fig.add_trace(
                    go.Scatter(
                        x=frame["x"],
                        y=frame["y"],
                        mode="lines",
                        name=str(col),
                        connectgaps=True,
                    )
                )
            elif chart_type == "bar":
                fig.add_trace(go.Bar(x=frame["x"], y=frame["y"], name=str(col)))
            else:
                raise ValueError(f"Unsupported chart type: {chart_type}")
            traces_added += 1

        if traces_added == 0:
            fig.add_annotation(
                text="No data available for requested columns",
                showarrow=False,
                font=dict(color="#c0392b", size=14),
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
            )

        if spec.get("show_legend") is not None:
            fig.update_layout(showlegend=bool(spec.get("show_legend")))

        if spec.get("yaxis_title"):
            fig.update_yaxes(title=spec["yaxis_title"])
        if spec.get("xaxis_title"):
            fig.update_xaxes(title=spec["xaxis_title"])

        # Professional axis formatting
        # Attempt to detect datetime-like x and format as dates
        if pd.api.types.is_datetime64_any_dtype(x_series):
            fig.update_xaxes(type="date", tickformat="%b %d, %Y", tickangle=-20)

        # Format Y axis to 2-decimal precision for prices and ensure nice grid
        fig.update_yaxes(tickformat=".2f", showgrid=True, gridcolor="rgba(200,200,200,0.2)")
        fig.update_xaxes(showgrid=True, gridcolor="rgba(200,200,200,0.2)")

        fig.update_layout(
            title=title,
            template="plotly_dark",
            margin=dict(l=40, r=20, t=60, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig.update_traces(line=dict(width=2.5))

        figure_json = fig.to_json()
        try:
            image_bytes = fig.to_image(format="png")
        except ValueError:
            image_bytes = fig.to_image(format="png")  # rely on kaleido; will raise if missing
        figure_png_b64 = base64.b64encode(image_bytes).decode("utf-8")
        return figure_json, figure_png_b64

    def _request_feedback(
        self,
        goal: str,
        spec: Dict[str, Any],
        figure_json: str,
        figure_png_b64: str,
        iteration: int,
    ) -> str:
        instructions = (
            "You are the visualization critic for FinSight."
            " Evaluate the attached chart image against the stated goal."
            " Respond EXACTLY in one of the following formats:\n"
            "APPROVED: <short justification>\n"
            "REVISE: <bullet list with actionable changes>."
        )

        image_part = {
            "mime_type": "image/png",
            "data": base64.b64decode(figure_png_b64.encode("utf-8")),
        }

        parts = [
            instructions,
            f"Iteration: {iteration}",
            f"Goal: {goal}",
            f"Current Spec: {spec}",
            image_part,
        ]
        return self.gemini.generate_multimodal(parts)

    def _apply_feedback(self, spec: Dict[str, Any], feedback: str) -> Dict[str, Any]:
        updated_spec = spec.copy()
        notes = updated_spec.setdefault("notes", [])
        notes.append(feedback)

        upper_feedback = feedback.upper()
        if "TITLE" in upper_feedback:
            updated_spec["title"] = spec.get("title", "Generated Chart") + " (Refined)"
        if "AXIS" in upper_feedback or "AXES" in upper_feedback:
            if "xaxis_title" not in updated_spec:
                updated_spec["xaxis_title"] = "Date"
            if "yaxis_title" not in updated_spec and spec.get("y"):
                updated_spec["yaxis_title"] = ", ".join(spec.get("y", []))
        if "COLOR" in upper_feedback:
            updated_spec["palette_hint"] = "corporate"
        if "ANNOT" in upper_feedback:
            annotations = updated_spec.setdefault("annotations", [])
            annotations.append({"text": "Key event", "xref": "paper", "yref": "paper", "x": 0.95, "y": 0.95})
        if "LEGEND" in upper_feedback:
            updated_spec["show_legend"] = True

        return updated_spec
