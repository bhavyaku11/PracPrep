"""Deterministic Demonstration Viva Provider Implementation.

Ports the frontend DemonstrationVivaProvider (IVivaAIProvider) into a pure Python
backend service conforming strictly to the BaseAIProvider interface and Pydantic v2 contracts.

This provider operates deterministically without external network calls or LLM APIs,
providing 100% reliable offline operation, fast automated testing, and transparent
circuit-breaker fallback when live AI providers fail.
"""

from dataclasses import dataclass
import math
import re
from typing import Callable, Optional
import uuid

from app.modules.ai.base import BaseAIProvider
from app.modules.ai.schemas import (
    AIEvaluationContextItem,
    AIExperimentContext,
    AIGeneratedQuestion,
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    EvaluationVerdictEnum,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    VivaDifficultyEnum,
    VivaProviderModeEnum,
    VivaTopicEnum,
    ParsedExperimentSections,
)

# Common stopwords to exclude from conceptual keyword matching
COMMON_STOPWORDS = frozenset(
    [
        "this", "that", "with", "from", "have", "were", "what", "when", "where",
        "which", "while", "about", "above", "after", "again", "against", "because",
        "been", "before", "being", "below", "between", "both", "during", "each",
        "further", "here", "into", "more", "most", "other", "some", "such", "than",
        "then", "their", "them", "there", "these", "they", "through", "under",
        "until", "very", "will", "would", "should", "could", "also", "using",
        "used", "value", "table", "given", "note", "read", "take", "step", "make",
        "must", "shall", "does", "done", "show", "tell", "give", "find",
    ]
)

# Standardized viva voce improvement tips cycled deterministically by question number
VIVA_IMPROVEMENT_TIPS = [
    "In oral viva voce, always define the scientific parameter first, then specify its standard SI units.",
    "Mention any underlying assumptions or boundary conditions when stating equations to oral examiners.",
    "Relate your answer directly to the physical instruments used on your test bench.",
    "State how errors are mitigated (e.g. eliminating parallax error, taking multiple readings).",
    "Explain the physical significance of the slope or intercept when describing graphs.",
    "Structure your oral response with a direct answer first, followed by supporting theoretical reasoning.",
    "Be prepared to explain what happens to your measurement if an anomalous reading occurs.",
    "Clearly distinguish between independent, dependent, and controlled variables when discussing procedures.",
]

# Regex for low-effort, dismissive, or gibberish answers
LOW_EFFORT_PATTERN = re.compile(
    r"^(idk|dont know|i don't know|no idea|asdf|qwerty|na|nil|dunno|not sure|\?+|\.+)\s*$",
    re.IGNORECASE,
)


def extract_significant_terms(text: Optional[str]) -> set[str]:
    """Extract significant keywords and conceptual terms from text.

    Filters punctuation, stopwords, and short words to identify meaningful
    technical tokens for rubric-based similarity calculation.
    """
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
    words = cleaned.split()
    return {
        w for w in words
        if len(w) > 3 and w not in COMMON_STOPWORDS and not w.isdigit()
    }


@dataclass(frozen=True)
class _QuestionTemplate:
    """Internal immutable template definition for question generation."""

    template_id: str
    topic: VivaTopicEnum
    difficulty: VivaDifficultyEnum
    grounded_source_section: str
    format_question: Callable[[AIExperimentContext], str]
    format_expected_answer: Callable[[AIExperimentContext], str]
    format_key_points: Callable[[AIExperimentContext], list[str]]


def _build_question_templates() -> list[_QuestionTemplate]:
    """Construct the comprehensive 40-template question bank across 5 topics."""

    def _get_title(exp: AIExperimentContext) -> str:
        return exp.title.strip() if exp.title else "this experiment"

    def _get_subject(exp: AIExperimentContext) -> str:
        return exp.subject.strip() if exp.subject else "laboratory engineering"

    templates: list[_QuestionTemplate] = [
        # ==============================================================================
        # 1. THEORY (8 templates)
        # ==============================================================================
        _QuestionTemplate(
            template_id="TH-01",
            topic=VivaTopicEnum.THEORY,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Objective",
            format_question=lambda exp: (
                f'What is the primary scientific aim or objective of "{_get_title(exp)}", '
                f'and what key parameter is being determined?'
            ),
            format_expected_answer=lambda exp: (
                f"The primary objective is: {exp.objective.strip()}"
                if exp.objective and exp.objective.strip()
                else f"The experiment aims to understand and demonstrate the fundamental concepts and working principles of {_get_title(exp)}."
            ),
            format_key_points=lambda exp: [
                "State the exact experimental objective",
                "Identify the independent and dependent variables",
                "Explain what property or parameter is being measured or verified",
            ],
        ),
        _QuestionTemplate(
            template_id="TH-02",
            topic=VivaTopicEnum.THEORY,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Theory",
            format_question=lambda exp: (
                f'Explain the fundamental governing scientific law or principle that forms '
                f'the basis of "{_get_title(exp)}".'
            ),
            format_expected_answer=lambda exp: (
                f"The underlying principle is based on: {exp.theory.strip()[:300]}..."
                if exp.theory and exp.theory.strip()
                else f"Understanding the circuit or system model and fundamental equations of {_get_subject(exp)} is essential."
            ),
            format_key_points=lambda exp: [
                "State the governing law or equation accurately",
                "Define the physical terms and symbols involved",
                "Explain the key theoretical assumptions",
            ],
        ),
        _QuestionTemplate(
            template_id="TH-03",
            topic=VivaTopicEnum.THEORY,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Theory",
            format_question=lambda exp: (
                f'What mathematical formulas or equations are used in "{_get_title(exp)}", '
                f'and what does each variable represent physically?'
            ),
            format_expected_answer=lambda exp: (
                f"The theoretical relations state: {exp.theory.strip()[:250]}"
                if exp.theory and exp.theory.strip()
                else f"The governing mathematical relationships describe the direct dependence between input and response variables in {_get_subject(exp)}."
            ),
            format_key_points=lambda exp: [
                "Write the primary mathematical relationship",
                "Specify the SI units for each variable",
                "State boundary conditions or constants used",
            ],
        ),
        _QuestionTemplate(
            template_id="TH-04",
            topic=VivaTopicEnum.THEORY,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Theory",
            format_question=lambda exp: (
                f'Under what boundary conditions or ideal assumptions does the theory of '
                f'"{_get_title(exp)}" hold true in a real laboratory environment?'
            ),
            format_expected_answer=lambda exp: (
                "The theory applies when standard conditions (e.g. constant temperature, ideal connections, "
                "linear range) are maintained as outlined in the theoretical documentation."
            ),
            format_key_points=lambda exp: [
                "Mention environmental factors (temperature, resistance, frequency)",
                "Identify sources of non-ideal behavior in real components",
                "Explain how theoretical models differ from physical setups",
            ],
        ),
        _QuestionTemplate(
            template_id="TH-05",
            topic=VivaTopicEnum.THEORY,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Subject",
            format_question=lambda exp: (
                f'What theoretical concepts in {_get_subject(exp)} are most critical to '
                f'understand before setting up "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                f"A strong understanding of fundamental laws, circuit/system equations, and "
                f"parameter definitions in {_get_subject(exp)} is required."
            ),
            format_key_points=lambda exp: [
                f"Identify relevant governing laws in {_get_subject(exp)}",
                "Explain the conceptual framework behind the experiment",
                "Relate the practical to textbook principles",
            ],
        ),
        _QuestionTemplate(
            template_id="TH-06",
            topic=VivaTopicEnum.THEORY,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Theory",
            format_question=lambda exp: (
                f'In the context of "{_get_title(exp)}", distinguish between the independent, '
                f'dependent, and controlled variables.'
            ),
            format_expected_answer=lambda exp: (
                "The independent variable is systematically varied by the operator, the dependent variable "
                "is measured as a response, and controlled variables are kept constant throughout."
            ),
            format_key_points=lambda exp: [
                "Identify the independent variable controlled during trials",
                "Identify the dependent variable recorded in the observation table",
                "State which parameters must remain constant to ensure valid results",
            ],
        ),
        _QuestionTemplate(
            template_id="TH-07",
            topic=VivaTopicEnum.THEORY,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Theory",
            format_question=lambda exp: (
                f'What dimensional constants or material properties are involved in "{_get_title(exp)}", '
                f'and how do they influence the system response?'
            ),
            format_expected_answer=lambda exp: (
                "Dimensional constants define the proportionality between physical quantities and serve as "
                "benchmarks for verifying component or material behavior."
            ),
            format_key_points=lambda exp: [
                "Name the specific physical constants involved",
                "State their standard SI units and typical order of magnitude",
                "Explain how material or environmental changes alter their effective values",
            ],
        ),
        _QuestionTemplate(
            template_id="TH-08",
            topic=VivaTopicEnum.THEORY,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Theory",
            format_question=lambda exp: (
                f'Provide an intuitive, qualitative explanation of what physical phenomena '
                f'occur during "{_get_title(exp)}".'
            ),
            format_expected_answer=lambda exp: (
                f"The experiment demonstrates the physical behavior where input energy or stimulus "
                f"propagates through the system, producing observable and measurable responses characteristic of {_get_subject(exp)}."
            ),
            format_key_points=lambda exp: [
                "Describe the physical mechanism without relying solely on mathematics",
                "Explain cause and effect in the experimental setup",
                "Connect the laboratory observation to real-world engineering applications",
            ],
        ),
        # ==============================================================================
        # 2. APPARATUS (8 templates)
        # ==============================================================================
        _QuestionTemplate(
            template_id="AP-01",
            topic=VivaTopicEnum.APPARATUS,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Apparatus",
            format_question=lambda exp: (
                f'List the key apparatus, meters, or components required for "{_get_title(exp)}" '
                f'and describe the function of each instrument.'
            ),
            format_expected_answer=lambda exp: (
                f"The required apparatus includes: {exp.apparatus.strip()[:250]}. "
                f"Each instrument is selected to measure or provide specific parameters."
                if exp.apparatus and exp.apparatus.strip()
                else "Standard calibrated measurement meters, power supplies, probes, and mounting breadboards/test benches are needed."
            ),
            format_key_points=lambda exp: [
                "Identify the instruments used",
                "Explain the measurement role of each meter or component",
                "Mention rating or sensitivity considerations",
            ],
        ),
        _QuestionTemplate(
            template_id="AP-02",
            topic=VivaTopicEnum.APPARATUS,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Apparatus",
            format_question=lambda exp: (
                f'Why are the specific measuring instruments chosen for "{_get_title(exp)}", '
                f'and how should you select their measurement ranges?'
            ),
            format_expected_answer=lambda exp: (
                "Instruments must be selected such that expected readings fall within the middle "
                "one-third of the meter scale to minimize percentage deflection error."
            ),
            format_key_points=lambda exp: [
                "Range selection based on maximum expected parameter",
                "Least count and sensitivity of meters",
                "Minimizing loading effects on the test circuit/setup",
            ],
        ),
        _QuestionTemplate(
            template_id="AP-03",
            topic=VivaTopicEnum.APPARATUS,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Apparatus",
            format_question=lambda exp: (
                f'How do you check for and correct zero-error or calibration offset on the '
                f'measuring instruments before conducting "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                "Inspect meters before applying power or load, adjust mechanical zero screws or "
                "digital tare buttons, and verify calibrated standards."
            ),
            format_key_points=lambda exp: [
                "Define zero-error and differentiate positive and negative offsets",
                "Describe mechanical or electronic tare adjustment",
                "Explain the consequence of uncorrected zero error on calculated results",
            ],
        ),
        _QuestionTemplate(
            template_id="AP-04",
            topic=VivaTopicEnum.APPARATUS,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Apparatus",
            format_question=lambda exp: (
                f'How does instrument internal resistance or loading effect alter measured values '
                f'in "{_get_title(exp)}", and how is it minimized?'
            ),
            format_expected_answer=lambda exp: (
                "Voltmeters require very high internal impedance to draw negligible current, while ammeters "
                "require near-zero resistance to avoid altering circuit potential drops."
            ),
            format_key_points=lambda exp: [
                "Explain voltmeter vs ammeter internal resistance requirements",
                "Analyze loading effect on parallel or series components",
                "Select appropriate meter sensitivity or digital buffering to minimize distortion",
            ],
        ),
        _QuestionTemplate(
            template_id="AP-05",
            topic=VivaTopicEnum.APPARATUS,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Apparatus",
            format_question=lambda exp: (
                f'What are the maximum voltage, current, power, or thermal ratings of the apparatus '
                f'used in "{_get_title(exp)}", and what happens if they are exceeded?'
            ),
            format_expected_answer=lambda exp: (
                "Components have strict continuous duty ratings; exceeding them causes non-linear distortion, "
                "thermal drift, dielectric breakdown, or permanent destruction."
            ),
            format_key_points=lambda exp: [
                "State the nominal operating ratings of critical components",
                "Identify failure modes associated with over-rating",
                "Explain protective mechanisms such as fuses, current limits, or heat sinks",
            ],
        ),
        _QuestionTemplate(
            template_id="AP-06",
            topic=VivaTopicEnum.APPARATUS,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Apparatus",
            format_question=lambda exp: (
                f'Compare the advantages and limitations of analog pointer meters versus digital '
                f'multimeters when used for "{_get_title(exp)}".'
            ),
            format_expected_answer=lambda exp: (
                "Analog meters provide continuous visual feedback of rate of change and fluctuations, "
                "while digital meters eliminate parallax error and offer higher input impedance."
            ),
            format_key_points=lambda exp: [
                "Contrast response time and ability to observe dynamic trends",
                "Discuss resolution, least count, and parallax elimination in digital meters",
                "Compare input impedance and noise susceptibility",
            ],
        ),
        _QuestionTemplate(
            template_id="AP-07",
            topic=VivaTopicEnum.APPARATUS,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Apparatus",
            format_question=lambda exp: (
                f'What standard auxiliary tools, connection leads, and power sources are required '
                f'on the test bench for "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                "Regulated DC/AC power supplies, low-resistance connecting patch cords with secure banana "
                "jacks, breadboards, and insulated probes are required."
            ),
            format_key_points=lambda exp: [
                "List essential connection leads and auxiliary hardware",
                "Explain the importance of secure, low-resistance terminal connections",
                "Identify power supply regulation requirements",
            ],
        ),
        _QuestionTemplate(
            template_id="AP-08",
            topic=VivaTopicEnum.APPARATUS,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Apparatus",
            format_question=lambda exp: (
                f'If sensors, probes, or transducers are utilized in "{_get_title(exp)}", '
                f'explain their conversion mechanism and transfer characteristic.'
            ),
            format_expected_answer=lambda exp: (
                "Transducers convert physical quantities into proportional electrical signals with "
                "defined sensitivity and linear range."
            ),
            format_key_points=lambda exp: [
                "Identify the input physical quantity and output electrical signal",
                "Explain the calibration factor or sensitivity curve",
                "Discuss limitations of the sensor bandwidth or operating range",
            ],
        ),
        # ==============================================================================
        # 3. PROCEDURE (8 templates)
        # ==============================================================================
        _QuestionTemplate(
            template_id="PR-01",
            topic=VivaTopicEnum.PROCEDURE,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Procedure",
            format_question=lambda exp: (
                f'Walk through the initial setup and preparation steps before taking the first '
                f'reading in "{_get_title(exp)}".'
            ),
            format_expected_answer=lambda exp: (
                f"Initial steps: {exp.procedure.strip()[:280]}..."
                if exp.procedure and exp.procedure.strip()
                else "Set up the apparatus cleanly, check all connections against schematic, verify meter zero errors, and have instructor inspect prior to power."
            ),
            format_key_points=lambda exp: [
                "Verifying zero-error on meters",
                "Checking connections against the circuit or schematic diagram",
                "Ensuring supply is off before final inspection",
            ],
        ),
        _QuestionTemplate(
            template_id="PR-02",
            topic=VivaTopicEnum.PROCEDURE,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Procedure",
            format_question=lambda exp: (
                f'What step-by-step sequence is followed to vary the independent variable and '
                f'record systematic observations in "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                f"The procedure specifies systematically adjusting the control parameter and noting corresponding dependent readings: {exp.procedure.strip()[:250]}"
                if exp.procedure and exp.procedure.strip()
                else "Systematically vary the independent parameter across its operating span in equal increments and record steady-state responses."
            ),
            format_key_points=lambda exp: [
                "Gradual increment of parameters",
                "Waiting for steady-state before reading",
                "Repeating readings to identify random errors",
            ],
        ),
        _QuestionTemplate(
            template_id="PR-03",
            topic=VivaTopicEnum.PROCEDURE,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Procedure",
            format_question=lambda exp: (
                f'If an unexpected or anomalous reading occurs during the procedure of '
                f'"{_get_title(exp)}", how should you systematically troubleshoot the setup?'
            ),
            format_expected_answer=lambda exp: (
                "Immediately isolate power, check loose connection terminals, verify meter polarity, "
                "and inspect component continuity."
            ),
            format_key_points=lambda exp: [
                "Isolate power before inspecting",
                "Check polarity and terminal tightness",
                "Verify meter ranges and calibration",
            ],
        ),
        _QuestionTemplate(
            template_id="PR-04",
            topic=VivaTopicEnum.PROCEDURE,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Procedure",
            format_question=lambda exp: (
                f'Describe the general experimental methodology you would adopt to verify '
                f'experimental results in "{_get_title(exp)}".'
            ),
            format_expected_answer=lambda exp: (
                "Set up the apparatus cleanly, check all connections, apply inputs incrementally, "
                "and record values in a systematic table."
            ),
            format_key_points=lambda exp: [
                "Systematic procedure execution",
                "Careful observation recording",
                "Maintaining reproducibility of test conditions",
            ],
        ),
        _QuestionTemplate(
            template_id="PR-05",
            topic=VivaTopicEnum.PROCEDURE,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Procedure",
            format_question=lambda exp: (
                f'Why is it critical to allow the experimental system in "{_get_title(exp)}" '
                f'to attain steady-state equilibrium before logging values?'
            ),
            format_expected_answer=lambda exp: (
                "Thermal, capacitive, or mechanical transients immediately after adjusting inputs cause "
                "false instantaneous readings that do not reflect true equilibrium."
            ),
            format_key_points=lambda exp: [
                "Differentiate transient response from steady-state equilibrium",
                "Explain the physical settling time required by components",
                "Avoid logging fluctuating or ramping values",
            ],
        ),
        _QuestionTemplate(
            template_id="PR-06",
            topic=VivaTopicEnum.PROCEDURE,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Procedure",
            format_question=lambda exp: (
                f'What exact protocol must be followed when reconfiguring circuit leads or '
                f'component connections during "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                "Completely de-energize the power source, discharge residual energy storage elements, "
                "re-route connections, and re-verify before restoring power."
            ),
            format_key_points=lambda exp: [
                "Mandatory power de-energization before touching terminals",
                "Discharging residual capacitors or inductors if present",
                "Secondary visual check of the rewired path against the schematic",
            ],
        ),
        _QuestionTemplate(
            template_id="PR-07",
            topic=VivaTopicEnum.PROCEDURE,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Procedure",
            format_question=lambda exp: (
                f'How does repeating procedural measurements in ascending and descending order '
                f'mitigate systematic errors in "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                "Taking readings in both directions detects and cancels hysteresis, thermal accumulation, "
                "and meter movement friction effects."
            ),
            format_key_points=lambda exp: [
                "Explain hysteresis in magnetic, thermal, or mechanical systems",
                "Describe averaging ascending and descending readings",
                "Distinguish systematic drift from random observation noise",
            ],
        ),
        _QuestionTemplate(
            template_id="PR-08",
            topic=VivaTopicEnum.PROCEDURE,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Procedure",
            format_question=lambda exp: (
                f'Describe the proper, safe shutdown and bench-clearing sequence upon completing '
                f'the experimental trials for "{_get_title(exp)}".'
            ),
            format_expected_answer=lambda exp: (
                "Reduce applied control supplies to minimum/zero, disconnect main power, safely dismantle "
                "patch cords, and return instruments to storage."
            ),
            format_key_points=lambda exp: [
                "Turn variable supplies down to minimum before opening switches",
                "Switch off mains power",
                "Disconnect leads cleanly without pulling on wire insulation",
            ],
        ),
        # ==============================================================================
        # 4. OBSERVATIONS (8 templates)
        # ==============================================================================
        _QuestionTemplate(
            template_id="OB-01",
            topic=VivaTopicEnum.OBSERVATIONS,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Observations & Calculations",
            format_question=lambda exp: (
                f'Explain how the recorded raw data is processed mathematically to arrive at the '
                f'final result of "{_get_title(exp)}".'
            ),
            format_expected_answer=lambda exp: (
                f"The calculation procedure applies the formula to tabular data: "
                f"{((exp.observations or '') + ' ' + (exp.calculations or '')).strip()[:250]}"
                if (exp.observations or exp.calculations)
                else "Tabular readings are averaged across trials and substituted into governing equations to calculate the final parameter with units."
            ),
            format_key_points=lambda exp: [
                "State the calculation formula used on table columns",
                "Explain the significance of averaging multiple trials",
                "Indicate how units are converted to standard SI format",
            ],
        ),
        _QuestionTemplate(
            template_id="OB-02",
            topic=VivaTopicEnum.OBSERVATIONS,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Observations",
            format_question=lambda exp: (
                f'What graphical plots or characteristic curves are drawn for "{_get_title(exp)}", '
                f'and what does the slope of the curve represent physically?'
            ),
            format_expected_answer=lambda exp: (
                "The plot shows the relationship between measured variables, where the slope directly "
                "corresponds to the physical constant or parameter being evaluated."
            ),
            format_key_points=lambda exp: [
                "Identify variables plotted on X and Y axes",
                "State whether the curve is linear or non-linear",
                "Physical interpretation of the slope and intercept",
            ],
        ),
        _QuestionTemplate(
            template_id="OB-03",
            topic=VivaTopicEnum.OBSERVATIONS,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Observations",
            format_question=lambda exp: (
                f'How would you structure a well-organized observation table for "{_get_title(exp)}" '
                f'to prevent recording ambiguous data?'
            ),
            format_expected_answer=lambda exp: (
                "Include serial numbers, descriptive column headings with explicit SI units, multiple trial "
                "columns, and a dedicated column for computed values."
            ),
            format_key_points=lambda exp: [
                "Column headings with proper units",
                "Provision for multiple trials and averages",
                "Clear distinction between measured vs calculated quantities",
            ],
        ),
        _QuestionTemplate(
            template_id="OB-04",
            topic=VivaTopicEnum.OBSERVATIONS,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Calculations",
            format_question=lambda exp: (
                f'How do you compute the percentage error between the experimental result of '
                f'"{_get_title(exp)}" and the theoretical standard value?'
            ),
            format_expected_answer=lambda exp: (
                "Percentage Error = |Theoretical Value - Experimental Value| / Theoretical Value * 100%. "
                "Explain reasons for any divergence."
            ),
            format_key_points=lambda exp: [
                "State the standard percentage error formula correctly",
                "Explain the benchmark or standard reference value used",
                "Identify key physical reasons causing experimental deviation",
            ],
        ),
        _QuestionTemplate(
            template_id="OB-05",
            topic=VivaTopicEnum.OBSERVATIONS,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Calculations",
            format_question=lambda exp: (
                f'How do measurement uncertainties in individual instruments propagate into the '
                f'final calculated parameter in "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                "Instrument least count contributes absolute errors; relative fractional uncertainties "
                "add in quadrature for independent multiplicative terms."
            ),
            format_key_points=lambda exp: [
                "Identify instrument least counts contributing to measurement uncertainty",
                "Explain error propagation rules for sums, differences, and products",
                "Express the final result with appropriate significant figures and error margin",
            ],
        ),
        _QuestionTemplate(
            template_id="OB-06",
            topic=VivaTopicEnum.OBSERVATIONS,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Observations",
            format_question=lambda exp: (
                f'If an individual data point in your observation table for "{_get_title(exp)}" '
                f'deviates drastically from the trend, how should you handle it?'
            ),
            format_expected_answer=lambda exp: (
                "Do not fabricate or arbitrarily discard points; inspect the apparatus immediately, repeat "
                "that specific trial under identical conditions, and document the cause."
            ),
            format_key_points=lambda exp: [
                "Refrain from arbitrary data deletion without technical justification",
                "Repeat the specific measurement under identical test settings",
                "Examine whether connection looseness or voltage surge caused the spike",
            ],
        ),
        _QuestionTemplate(
            template_id="OB-07",
            topic=VivaTopicEnum.OBSERVATIONS,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Observations",
            format_question=lambda exp: (
                f'Why is taking multiple trials and computing mean values standard practice when '
                f'recording observations in "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                "Averaging across multiple independent measurements reduces random Gaussian errors and "
                "provides a more statistically robust estimate."
            ),
            format_key_points=lambda exp: [
                "Explain how averaging diminishes random observational noise",
                "Increase confidence in the measured mean value",
                "Distinguish random errors reduced by averaging from systematic errors that persist",
            ],
        ),
        _QuestionTemplate(
            template_id="OB-08",
            topic=VivaTopicEnum.OBSERVATIONS,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Calculations",
            format_question=lambda exp: (
                f'How do you verify the dimensional consistency of the calculation equations '
                f'used for "{_get_title(exp)}" across unit conversions?'
            ),
            format_expected_answer=lambda exp: (
                "Substitute fundamental dimensions [M, L, T, I] into both sides of the calculation equation "
                "to ensure both sides are dimensionally homogeneous."
            ),
            format_key_points=lambda exp: [
                "State the fundamental dimensions of all participating variables",
                "Verify that both sides of the calculation formula have identical dimensions",
                "Confirm that prefix multipliers (milli-, micro-, kilo-) are correctly transformed into SI base units",
            ],
        ),
        # ==============================================================================
        # 5. PRECAUTIONS (8 templates)
        # ==============================================================================
        _QuestionTemplate(
            template_id="PC-01",
            topic=VivaTopicEnum.PRECAUTIONS,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Precautions",
            format_question=lambda exp: (
                f'What are the critical safety precautions and handling instructions that must be '
                f'observed during "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                f"The key precautions include: {exp.precautions.strip()[:250]}"
                if exp.precautions and exp.precautions.strip()
                else "Verify circuit connections with the lab instructor before turning on power, wear safety gear, and ensure zero error on meters."
            ),
            format_key_points=lambda exp: [
                "Preventing electrical shock or short-circuits",
                "Operating components strictly within rated voltage/current",
                "Parallax error prevention when reading analog meters",
            ],
        ),
        _QuestionTemplate(
            template_id="PC-02",
            topic=VivaTopicEnum.PRECAUTIONS,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Precautions",
            format_question=lambda exp: (
                f'What specific precautions are necessary to prevent instrument damage or severe '
                f'measurement error in "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                "Ensure correct polarity connections, start power supply from zero, and avoid exceeding "
                "maximum instrument deflection."
            ),
            format_key_points=lambda exp: [
                "Polarity verification",
                "Zero-setting and parallax elimination",
                "Gradual voltage/load application",
            ],
        ),
        _QuestionTemplate(
            template_id="PC-03",
            topic=VivaTopicEnum.PRECAUTIONS,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Precautions",
            format_question=lambda exp: (
                f'What general laboratory safety precautions should always be followed when working '
                f'on {_get_subject(exp)} practicals?'
            ),
            format_expected_answer=lambda exp: (
                "Power off during wiring changes, inspect before energizing, avoid loose wires, keep liquids "
                "away from benches, and wear appropriate personal safety gear."
            ),
            format_key_points=lambda exp: [
                "Power off during wiring changes",
                "Inspection before energizing",
                "Maintain a clean and organized work bench",
            ],
        ),
        _QuestionTemplate(
            template_id="PC-04",
            topic=VivaTopicEnum.PRECAUTIONS,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Precautions",
            format_question=lambda exp: (
                f'Explain what parallax error is when taking readings on analog meters for '
                f'"{_get_title(exp)}", and how it is eliminated.'
            ),
            format_expected_answer=lambda exp: (
                "Parallax occurs when the observer's line of sight is not perpendicular to the scale; "
                "align your eye directly over the pointer using the anti-parallax mirror."
            ),
            format_key_points=lambda exp: [
                "Define parallax as optical angular displacement",
                "Describe viewing the meter needle perpendicular to the scale",
                "Use the mirror strip beneath the pointer so the needle hides its reflection",
            ],
        ),
        _QuestionTemplate(
            template_id="PC-05",
            topic=VivaTopicEnum.PRECAUTIONS,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Precautions",
            format_question=lambda exp: (
                f'What precautions must be observed regarding heat dissipation and prolonged '
                f'component energization in "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                "Prolonged energization causes resistive heating that shifts component values and damages "
                "insulation; de-energize circuits between observation sets."
            ),
            format_key_points=lambda exp: [
                "Explain how temperature rise causes parameter drift and measurement error",
                "Avoid leaving high current flowing between observation steps",
                "Ensure adequate air circulation around power components and heat sinks",
            ],
        ),
        _QuestionTemplate(
            template_id="PC-06",
            topic=VivaTopicEnum.PRECAUTIONS,
            difficulty=VivaDifficultyEnum.INTERMEDIATE,
            grounded_source_section="Precautions",
            format_question=lambda exp: (
                f'What personal safety measures and grounding precautions are required to avoid '
                f'electrical shock during "{_get_title(exp)}"?'
            ),
            format_expected_answer=lambda exp: (
                "Ensure all equipment chassis are solidly earth-grounded, wear rubber-soled footwear, never "
                "touch live conductors, and work with dry hands."
            ),
            format_key_points=lambda exp: [
                "Verify equipment protective earth grounding",
                "Avoid touching exposed live conductors or uninsulated terminals",
                "Never conduct electrical practicals with wet hands or near liquid spills",
            ],
        ),
        _QuestionTemplate(
            template_id="PC-07",
            topic=VivaTopicEnum.PRECAUTIONS,
            difficulty=VivaDifficultyEnum.ADVANCED,
            grounded_source_section="Precautions",
            format_question=lambda exp: (
                f'What hazard is posed by rapidly interrupting inductive circuits or discharging '
                f'capacitors during "{_get_title(exp)}", and how is it safely handled?'
            ),
            format_expected_answer=lambda exp: (
                "Collapsing magnetic fields generate high-voltage inductive kickback spikes; use freewheeling "
                "diodes or safe bleeder resistors before opening contacts."
            ),
            format_key_points=lambda exp: [
                "Explain inductive kickback (V = -L * di/dt) during sudden switch openings",
                "Describe capacitive charge retention hazards after power cutoff",
                "Use proper damping or bleeder discharge paths before touching terminals",
            ],
        ),
        _QuestionTemplate(
            template_id="PC-08",
            topic=VivaTopicEnum.PRECAUTIONS,
            difficulty=VivaDifficultyEnum.BEGINNER,
            grounded_source_section="Precautions",
            format_question=lambda exp: (
                f'Why is pre-energization verification by a lab instructor or lab partner mandatory '
                f'before powering on the "{_get_title(exp)}" setup?'
            ),
            format_expected_answer=lambda exp: (
                "A second independent check verifies that meter polarities, circuit topologies, and supply "
                "ratings are correct, preventing immediate component burnout."
            ),
            format_key_points=lambda exp: [
                "Independent check identifies cross-wiring or polarity reversals",
                "Prevents accidental short circuits across power supplies",
                "Enforces shared laboratory accountability and safety compliance",
            ],
        ),
    ]
    return templates


class DemonstrationAIProvider(BaseAIProvider):
    """Deterministic Demonstration Viva Examination Provider.

    Provides offline, heuristic-grounded question generation and answer evaluation
    matching the frontend demonstration engine. Produces 100% reproducible results
    without network calls, external tokens, or LLM latency.
    """

    def __init__(self) -> None:
        self._templates = _build_question_templates()

    @property
    def provider_id(self) -> str:
        """Machine identifier for provider resolution and telemetry."""
        return "demonstration"

    @property
    def display_name(self) -> str:
        """Human-readable display title for student UI presentation."""
        return "PracPrep Demonstration Engine"

    @property
    def provider_mode(self) -> VivaProviderModeEnum:
        """Operational category: demonstration (heuristic/offline)."""
        return VivaProviderModeEnum.DEMONSTRATION

    async def generate_questions(
        self,
        request: QuestionGenerationRequest,
    ) -> QuestionGenerationResponse:
        """Generate deterministic viva questions grounded in experiment manual content.

        Selection Strategy:
        1. Prioritize templates matching topic_focus (if not 'mixed').
        2. Within matched topics, prioritize templates matching requested difficulty (if not 'mixed').
        3. If more templates are required to satisfy question_count, draw from other difficulties
           within the focused topic, then from other topics in round-robin order.
        4. Guarantee that every question in the returned set has a unique question_text.
        5. Generate deterministic UUIDs for question IDs based on experiment and question text.
        """
        experiment = request.experiment
        requested_count = request.question_count
        topic_focus = request.topic_focus
        difficulty = request.difficulty

        # Partition templates into priority tiers
        matching_topic = [
            t for t in self._templates
            if topic_focus == VivaTopicEnum.MIXED or t.topic == topic_focus
        ]

        if not matching_topic:
            matching_topic = list(self._templates)

        # Tier 1: exact topic match and exact difficulty match
        tier1 = [
            t for t in matching_topic
            if difficulty == VivaDifficultyEnum.MIXED or t.difficulty == difficulty
        ]
        # Tier 2: exact topic match, other difficulties
        tier2 = [t for t in matching_topic if t not in tier1]
        # Tier 3: other topics matching difficulty
        tier3 = [
            t for t in self._templates
            if t not in matching_topic and (difficulty == VivaDifficultyEnum.MIXED or t.difficulty == difficulty)
        ]
        # Tier 4: all remaining templates
        tier4 = [
            t for t in self._templates
            if t not in tier1 and t not in tier2 and t not in tier3
        ]

        ordered_candidates = tier1 + tier2 + tier3 + tier4

        # Select unique candidates up to requested_count
        selected_templates: list[_QuestionTemplate] = []
        seen_texts: set[str] = set()

        for tmpl in ordered_candidates:
            q_text = tmpl.format_question(experiment)
            if q_text not in seen_texts:
                seen_texts.add(q_text)
                selected_templates.append(tmpl)
                if len(selected_templates) == requested_count:
                    break

        questions: list[AIGeneratedQuestion] = []
        exp_title = experiment.title.strip() if experiment.title else "experiment"

        for idx, tmpl in enumerate(selected_templates, start=1):
            q_text = tmpl.format_question(experiment)
            expected_ans = tmpl.format_expected_answer(experiment)
            key_pts = tmpl.format_key_points(experiment)

            # Generate deterministic UUID5 for reproducible IDs
            q_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"demo:{exp_title}:{idx}:{tmpl.template_id}"))

            questions.append(
                AIGeneratedQuestion(
                    id=q_id,
                    question_number=idx,
                    question_text=q_text,
                    topic=tmpl.topic,
                    difficulty=tmpl.difficulty,
                    expected_answer=expected_ans,
                    key_points=key_pts,
                    grounded_source_section=tmpl.grounded_source_section,
                )
            )

        return QuestionGenerationResponse(
            questions=questions,
            provider_mode=self.provider_mode,
            provider_id=self.provider_id,
            metadata={
                "engine": "deterministic_demonstration_v1",
                "template_count": len(self._templates),
                "is_offline_demonstration": True,
            },
        )

    async def evaluate_answer(
        self,
        request: AnswerEvaluationRequest,
    ) -> AnswerEvaluationResponse:
        """Evaluate a student's answer using deterministic keyword & rubric matching.

        Evaluation Rules:
        - Very short answers (< 5 chars): Score 0, INCORRECT, no points.
        - Low-effort dismissive answers ("idk", "asdf"): Score 1, INCORRECT.
        - Irrelevant answers (zero matching terms and zero key points covered): Score 0, INCORRECT.
        - Substantive answers:
          - Target terms extracted from expected answer + key points.
          - Key point coverage computed via significant term overlap threshold (35%).
          - Score computed as weighted composite:
            (key_point_ratio * 5.0) + (term_match_ratio * 3.0) + (length_bonus * 2.0).
          - Clamped to [0, 10].
          - Verdict assigned: >= 8 CORRECT, <= 3 INCORRECT, 4-7 PARTIALLY_CORRECT.
        """
        question = request.question
        clean_answer = request.student_answer.strip()

        # Handle low-effort or dismissive phrases
        if LOW_EFFORT_PATTERN.match(clean_answer):
            missing_text = (
                f"You missed the core explanation: {', '.join(question.key_points)}."
                if question.key_points
                else "You did not supply technical concepts from the laboratory manual."
            )
            return AnswerEvaluationResponse(
                verdict=EvaluationVerdictEnum.INCORRECT,
                score=1,
                feedback="The response does not provide the required technical concepts. Review the laboratory manual sections for this experiment.",
                what_you_got_right="Attempted response, but without technical substance.",
                what_was_missing=missing_text,
                expected_answer=question.expected_answer or "",
                improvement_tip="Even if uncertain, mention the primary formula, law, or equipment involved.",
                key_points_covered=[],
                key_points_missed=list(question.key_points),
                provider_mode=self.provider_mode,
                provider_id=self.provider_id,
                metadata={"evaluation_method": "low_effort_gate"},
            )

        # Handle very short responses (< 5 characters)
        if len(clean_answer) < 5:
            missing_text = (
                f"A complete answer should address: {'; '.join(question.key_points)}."
                if question.key_points
                else "Provide an in-depth scientific explanation with appropriate terminology."
            )
            return AnswerEvaluationResponse(
                verdict=EvaluationVerdictEnum.INCORRECT,
                score=0,
                feedback="Your response is too brief to demonstrate technical understanding. Oral viva exams require structured explanations with scientific terminology.",
                what_you_got_right="No substantive technical response was provided.",
                what_was_missing=missing_text,
                expected_answer=question.expected_answer or "",
                improvement_tip="State the core scientific definition or working principle before elaborating.",
                key_points_covered=[],
                key_points_missed=list(question.key_points),
                provider_mode=self.provider_mode,
                provider_id=self.provider_id,
                metadata={"evaluation_method": "length_gate", "raw_length": len(clean_answer)},
            )

        # Extract significant terms
        answer_terms = extract_significant_terms(clean_answer)
        expected_terms = extract_significant_terms(question.expected_answer)
        key_point_terms: set[str] = set()
        for kp in question.key_points:
            key_point_terms.update(extract_significant_terms(kp))

        target_terms = expected_terms | key_point_terms

        # Concept overlap matching
        matched_terms = answer_terms & target_terms
        matched_count = len(matched_terms)

        recognized_concepts = [t for t in sorted(matched_terms) if len(t) > 3][:4]
        missing_concepts = [t for t in sorted(target_terms - answer_terms) if len(t) > 4][:3]

        # Key point coverage evaluation
        covered_points: list[str] = []
        for kp in question.key_points:
            kp_terms = extract_significant_terms(kp)
            if not kp_terms:
                continue
            hits = len(kp_terms & answer_terms)
            threshold = max(1, math.floor(len(kp_terms) * 0.35))
            if hits >= threshold:
                covered_points.append(kp)

        missed_points = [kp for kp in question.key_points if kp not in covered_points]

        # Check for completely irrelevant responses (zero overlap with target terms and 0 key points covered)
        if target_terms and matched_count == 0 and not covered_points:
            missing_text = (
                f"The response did not address the question asked. Expected coverage: {'; '.join(question.key_points)}."
                if question.key_points
                else "The response does not address the required topic."
            )
            return AnswerEvaluationResponse(
                verdict=EvaluationVerdictEnum.INCORRECT,
                score=0,
                feedback="The submitted response is off-topic or irrelevant to the question asked. Ensure you focus directly on the laboratory principles in question.",
                what_you_got_right="No relevant technical principles were identified in the response.",
                what_was_missing=missing_text,
                expected_answer=question.expected_answer or "",
                improvement_tip="Focus directly on the question asked and reference the relevant formulas, apparatus, or procedural steps.",
                key_points_covered=[],
                key_points_missed=list(question.key_points),
                provider_mode=self.provider_mode,
                provider_id=self.provider_id,
                metadata={"evaluation_method": "relevance_gate", "matched_term_count": 0},
            )

        # Compute composite score
        match_ratio = (matched_count / len(target_terms)) if target_terms else 0.5
        key_point_ratio = (len(covered_points) / len(question.key_points)) if question.key_points else 0.5
        word_count = len(clean_answer.split())
        length_bonus = min(word_count / 25.0, 1.0)

        raw_score = (key_point_ratio * 5.0) + (match_ratio * 3.0) + (length_bonus * 2.0)
        score = int(round(raw_score))
        score = max(0, min(10, score))

        # Determine verdict
        if score >= 8:
            verdict = EvaluationVerdictEnum.CORRECT
        elif score <= 3:
            verdict = EvaluationVerdictEnum.INCORRECT
        else:
            verdict = EvaluationVerdictEnum.PARTIALLY_CORRECT

        # Formulate what_you_got_right
        if covered_points or recognized_concepts:
            summary_items = (
                covered_points[:2]
                if covered_points
                else [f'"{c}"' for c in recognized_concepts[:3]]
            )
            what_you_got_right = f"Accurately addressed key principles: {', '.join(summary_items)}."
        else:
            what_you_got_right = "You provided general context, but lacked specific technical terminology from the lab manual."

        # Formulate what_was_missing
        if missed_points or missing_concepts:
            missing_items = (
                missed_points
                if missed_points
                else [f'"{c}"' for c in missing_concepts]
            )
            what_was_missing = f"Missing critical concepts: {'; '.join(missing_items)}."
        else:
            what_was_missing = "No major concepts were omitted."

        # Formulate comprehensive feedback
        topic_name = question.topic.value if hasattr(question.topic, "value") else str(question.topic)
        if verdict == EvaluationVerdictEnum.CORRECT:
            feedback = f"Excellent explanation. You demonstrated strong comprehension of {topic_name} concepts. {what_you_got_right}"
        elif verdict == EvaluationVerdictEnum.PARTIALLY_CORRECT:
            feedback = f"Partially correct answer. {what_you_got_right} {what_was_missing}"
        else:
            feedback = f"Incorrect or incomplete response. {what_was_missing}"

        # Improvement tip selection
        tip_index = (question.question_number - 1) % len(VIVA_IMPROVEMENT_TIPS)
        improvement_tip = VIVA_IMPROVEMENT_TIPS[tip_index]

        return AnswerEvaluationResponse(
            verdict=verdict,
            score=score,
            feedback=feedback,
            what_you_got_right=what_you_got_right,
            what_was_missing=what_was_missing,
            expected_answer=question.expected_answer or "",
            improvement_tip=improvement_tip,
            key_points_covered=covered_points,
            key_points_missed=missed_points,
            provider_mode=self.provider_mode,
            provider_id=self.provider_id,
            metadata={
                "evaluation_method": "deterministic_keyword_rubric",
                "matched_term_count": matched_count,
                "key_points_covered_count": len(covered_points),
                "word_count": word_count,
            },
        )

    async def parse_manual_sections(
        self,
        raw_text: str,
        file_name: Optional[str] = None,
    ) -> ParsedExperimentSections:
        """Parse extracted laboratory manual text into structured experiment sections.

        Uses deterministic regex and structural heuristics to extract standard lab manual
        sections without external network calls or LLM dependencies.
        """
        if not raw_text or not raw_text.strip():
            return ParsedExperimentSections()

        # Regex for headings
        section_headers = [
            ("objective", re.compile(r"^(?:experiment\s+aim|aim|objective|object)\s*[:\-\.]?\s*(.*)$", re.IGNORECASE)),
            ("theory", re.compile(r"^(?:theory|principle|theoretical\s+background|governing\s+principles?)\s*[:\-\.]?\s*(.*)$", re.IGNORECASE)),
            ("apparatus", re.compile(r"^(?:apparatus\s+required|apparatus|equipment\s+required|equipment|components|materials\s+required|materials)\s*[:\-\.]?\s*(.*)$", re.IGNORECASE)),
            ("procedure", re.compile(r"^(?:experimental\s+procedure|procedure|methodology|method|steps)\s*[:\-\.]?\s*(.*)$", re.IGNORECASE)),
            ("observations", re.compile(r"^(?:observations?\s+and\s+calculations?|observations?|observation\s+table|readings|data\s+table)\s*[:\-\.]?\s*(.*)$", re.IGNORECASE)),
            ("calculations", re.compile(r"^(?:calculations?|formulae?|formula\s+used|error\s+analysis)\s*[:\-\.]?\s*(.*)$", re.IGNORECASE)),
            ("precautions", re.compile(r"^(?:precautions?\s+and\s+sources\s+of\s+errors?|safety\s+precautions?|precautions?|safety\s+guidelines?)\s*[:\-\.]?\s*(.*)$", re.IGNORECASE)),
            ("result", re.compile(r"^(?:results?\s+and\s+discussions?|results?|conclusions?|inferences?)\s*[:\-\.]?\s*(.*)$", re.IGNORECASE)),
            ("additional_notes", re.compile(r"^(?:notes?|additional\s+notes?|viva\s+questions?|references?)\s*[:\-\.]?\s*(.*)$", re.IGNORECASE)),
        ]

        # Scan text lines and partition into sections
        sections_map: dict[str, list[str]] = {k: [] for k, _ in section_headers}
        current_section: Optional[str] = None
        pre_section_lines: list[str] = []

        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                if current_section:
                    sections_map[current_section].append("")
                continue

            matched_header = None
            header_content = ""
            for sec_name, pattern in section_headers:
                m = pattern.match(stripped)
                if m:
                    matched_header = sec_name
                    header_content = m.group(1).strip()
                    break

            if matched_header:
                current_section = matched_header
                if header_content:
                    sections_map[current_section].append(header_content)
            else:
                if current_section:
                    sections_map[current_section].append(line)
                else:
                    pre_section_lines.append(stripped)

        # Inspect pre_section_lines for title, exp number, subject
        title: Optional[str] = None
        experiment_number: Optional[str] = None
        subject: Optional[str] = None

        for p_line in pre_section_lines:
            exp_line_m = re.match(
                r"^(?:Experiment|Exp)\s*(?:No\.?|Number|#)?\s*[:\-\s]*\s*([0-9A-Za-z\-_]+)?\s*[:\-\.]?\s*(.*)$",
                p_line,
                re.IGNORECASE,
            )
            if exp_line_m:
                if exp_line_m.group(1) and not experiment_number:
                    experiment_number = exp_line_m.group(1).strip()
                after_exp = (exp_line_m.group(2) or "").strip()
                if after_exp and not title:
                    title = after_exp
                continue

            subj_m = re.match(r"^(?:Subject|Course|Department)\s*[:\-\s]*\s*([^\n]+)", p_line, re.IGNORECASE)
            if subj_m and not subject:
                subject = subj_m.group(1).strip()
                continue

            title_m = re.match(r"^(?:Title|Experiment\s*Name)\s*[:\-\s]*\s*([^\n]+)", p_line, re.IGNORECASE)
            if title_m and not title:
                title = title_m.group(1).strip()
                continue

            if not title and len(p_line) < 120:
                lower_p = p_line.lower()
                if not any(lower_p.startswith(prefix) for prefix in ["subject", "course", "department", "date", "page", "lab"]):
                    title = p_line

        # Fallbacks for Title
        if not title:
            if pre_section_lines:
                title = pre_section_lines[0]
            elif file_name:
                cleaned_name = re.sub(r"\.[^.]+$", "", file_name)
                title = cleaned_name.replace("_", " ").replace("-", " ").title()
            else:
                title = "Laboratory Experiment"

        # Truncate title if overly long
        if len(title) > 255:
            title = title[:252] + "..."

        # Subject inference
        if not subject:
            lower_text = raw_text.lower()
            if any(w in lower_text for w in ["resistance", "current", "voltage", "circuit", "ohm", "diode", "transistor", "gate"]):
                subject = "Electrical & Electronics Engineering"
            elif any(w in lower_text for w in ["lens", "prism", "wavelength", "pendulum", "velocity", "acceleration", "friction", "newton"]):
                subject = "Physics"
            elif any(w in lower_text for w in ["titration", "acid", "base", "solution", "reaction", "molarity", "ph value"]):
                subject = "Chemistry"
            elif any(w in lower_text for w in ["algorithm", "sorting", "stack", "queue", "database", "binary search"]):
                subject = "Computer Science"
            else:
                subject = "Applied Science"

        def _clean_sec(key: str) -> Optional[str]:
            lines_list = sections_map.get(key, [])
            joined = "\n".join(lines_list).strip()
            return joined if joined else None

        return ParsedExperimentSections(
            title=title,
            subject=subject,
            experiment_number=experiment_number,
            objective=_clean_sec("objective"),
            theory=_clean_sec("theory"),
            apparatus=_clean_sec("apparatus"),
            procedure=_clean_sec("procedure"),
            observations=_clean_sec("observations"),
            calculations=_clean_sec("calculations"),
            precautions=_clean_sec("precautions"),
            result=_clean_sec("result"),
            additional_notes=_clean_sec("additional_notes"),
        )
