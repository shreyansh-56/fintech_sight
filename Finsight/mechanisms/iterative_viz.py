"""Iterative Vision-Enhanced Mechanism for FinSight."""
from __future__ import annotations

import base64
import io
import json
import re
from typing import Any, Dict, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from Finsight.tools.unified_llm_client import UnifiedLLMClient


class IterativeVizMechanism:
    """
    P(C_vis | V) = ∏_{t=1}^{M} P_θ(C_t^vis | C_{t-1}^vis, F_{t-1}, V)
    where F_{t-1} = VLM(Execute(C_{t-1}^vis))
    
    Iteratively refines chart code until professional quality is reached.
    Max iterations: 3 (from paper Appendix C)
    """

    CRITIQUE_PROMPT = """
You are a professional financial chart reviewer. Analyze this chart and identify issues.
Focus on:
1. Information density — is there enough data shown? Are auxiliary lines/averages missing?
2. Legend clarity — are all data series labeled? Is the legend clear?
3. Color scheme — is it appropriate for financial data? Professional enough?
4. Redundancy — are there unnecessary subplots or repeated information?
5. Context — are axis labels, title, and units present and correct?

Output a JSON with:
{
  "quality": "professional" | "needs_improvement",
  "issues": ["issue 1", "issue 2", ...],
  "suggestions": ["specific code change 1", "specific code change 2", ...]
}
"""

    def __init__(self, vlm_client: UnifiedLLMClient, llm_client: UnifiedLLMClient, max_iterations: int = 3):
        self.vlm = vlm_client
        self.llm = llm_client
        self.max_iterations = max_iterations

    def refine(self, initial_code: str, data_context: str, chart_spec: str) -> Tuple[str, bytes]:
        """
        Takes initial chart plotting code and iteratively refines it.
        Returns (final_code, final_image_bytes).
        """
        code = initial_code
        
        for iteration in range(self.max_iterations):
            # Execute the current plotting code → get image
            image_bytes = self._execute_plot(code)
            
            # VLM critiques the image
            feedback = self._critique_chart(image_bytes)
            
            # If professional quality reached, stop
            if feedback.get("quality") == "professional":
                print(f"Chart approved at iteration {iteration + 1}")
                break
            
            # LLM regenerates code based on feedback
            code = self._regenerate_code(
                current_code=code,
                issues=feedback.get("issues", []),
                suggestions=feedback.get("suggestions", []),
                data_context=data_context,
                chart_spec=chart_spec
            )
        
        return code, image_bytes

    def _execute_plot(self, code: str) -> bytes:
        """Execute matplotlib/seaborn code and return PNG bytes."""
        plt.clf()
        local_ns = {
            "plt": plt,
            "pd": pd,
            "np": __import__("numpy"),
            "sns": __import__("seaborn", fromlist=[""]),
        }
        exec(code, local_ns)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        return buf.read()

    def _critique_chart(self, image_bytes: bytes) -> Dict[str, Any]:
        """Send image to VLM for critique. Returns parsed JSON feedback."""
        b64_image = base64.b64encode(image_bytes).decode()
        response = self.vlm.complete_with_image(
            prompt=self.CRITIQUE_PROMPT,
            image_b64=b64_image,
            image_type="image/png"
        )
        
        # Parse JSON from response
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {"quality": "needs_improvement", "issues": ["Could not parse feedback"], "suggestions": []}

    def _regenerate_code(self, current_code: str, issues: list, suggestions: list, 
                         data_context: str, chart_spec: str) -> str:
        """Ask LLM to fix the chart code given the VLM feedback."""
        prompt = f"""
You are a professional financial data visualization expert.

Current chart code:
```python
{current_code}
```

VLM Critic identified these issues:
{chr(10).join(f'- {issue}' for issue in issues)}

Suggested improvements:
{chr(10).join(f'- {s}' for s in suggestions)}

Data context:
{data_context}

Chart specification:
{chart_spec}

Rewrite the complete chart code to fix all issues. 
Use matplotlib and seaborn. Use professional financial color schemes.
Return ONLY the Python code, no explanation.
"""
        return self.llm.generate(prompt)
