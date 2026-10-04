import assert from "node:assert";
import {
  calculateOverviewMetrics,
  calculateExperimentReadiness,
  extractPerformanceTrendPoints,
  aggregateTopicPerformance,
  extractRevisionPriorities,
  extractStrongTopics,
  generateRecommendedNextSteps,
  filterSessionsByPeriod,
} from "./src/utils/progressAnalytics.ts";

console.log("Running unit tests for progressAnalytics...");

// Test Case 1: Empty Data
{
  const emptyMetrics = calculateOverviewMetrics([], [], "all");
  assert.strictEqual(emptyMetrics.totalExperiments, 0);
  assert.strictEqual(emptyMetrics.completedExperiments, 0);
  assert.strictEqual(emptyMetrics.vivaSessionsCount, 0);
  assert.strictEqual(emptyMetrics.completedVivaSessionsCount, 0);
  assert.strictEqual(emptyMetrics.averageVivaScore, null);
  assert.strictEqual(emptyMetrics.preparationPercentage, 0);

  const emptyReadiness = calculateExperimentReadiness([], []);
  assert.strictEqual(emptyReadiness.length, 0);

  const emptyTrends = extractPerformanceTrendPoints([], "all");
  assert.strictEqual(emptyTrends.length, 0);

  const emptyTopics = aggregateTopicPerformance([], "all");
  assert.strictEqual(emptyTopics.length, 5);
  emptyTopics.forEach((t) => {
    assert.strictEqual(t.questionsAnswered, 0);
    assert.strictEqual(t.status, "unpracticed");
    assert.strictEqual(t.averageScore, null);
  });

  const emptyPriorities = extractRevisionPriorities([], []);
  assert.strictEqual(emptyPriorities.length, 0);

  const emptyStrong = extractStrongTopics([], emptyTopics);
  assert.strictEqual(emptyStrong.length, 0);

  const emptySteps = generateRecommendedNextSteps([], [], []);
  assert.strictEqual(emptySteps.length, 0);
  console.log("✓ Test Case 1 Passed: Empty Data handled gracefully");
}

// Test Case 2: Incomplete Sessions vs Completed Sessions
{
  const mockExp = [
    {
      id: "exp_1",
      title: "Ohm's Law",
      subject: "Physics",
      status: "in-progress",
      createdAt: "2026-10-01",
      createdAtTimestamp: 1000,
      updatedAt: "2026-10-01",
      updatedAtTimestamp: 1000,
      vivaQuestionsCount: 5,
      preparationChecklist: { objective: true, theory: true },
    },
  ];

  const mockSessions = [
    // Incomplete session (score 2.0 should NOT count in average)
    {
      id: "sess_incomplete",
      experimentId: "exp_1",
      experimentTitle: "Ohm's Law",
      subject: "Physics",
      config: { questionCount: 5, difficulty: "beginner", focus: "mixed" },
      startedAt: Date.now() - 10000,
      isCompleted: false,
      answers: [],
      totalQuestions: 5,
      questionsAnswered: 1,
      correctCount: 0,
      partiallyCorrectCount: 0,
      incorrectCount: 1,
      averageScore: 2.0,
      topicAnalysis: {},
      weakTopics: [],
      strongTopics: [],
      revisionRecommendations: [],
      providerMode: "demonstration",
    },
    // Completed session (score 8.0)
    {
      id: "sess_completed",
      experimentId: "exp_1",
      experimentTitle: "Ohm's Law",
      subject: "Physics",
      config: { questionCount: 5, difficulty: "beginner", focus: "mixed" },
      startedAt: Date.now() - 5000,
      completedAt: Date.now() - 4000,
      isCompleted: true,
      answers: [
        {
          questionId: "q1",
          questionNumber: 1,
          questionText: "State Ohm's Law",
          topic: "theory",
          difficulty: "beginner",
          studentAnswer: "V = IR",
          evaluation: {
            verdict: "correct",
            score: 10,
            whatYouGotRight: "Stated V=IR correctly",
            whatWasMissing: "",
            expectedAnswer: "V=IR",
            improvementTip: "",
            providerMode: "demonstration",
          },
          timestamp: Date.now() - 4500,
        },
        {
          questionId: "q2",
          questionNumber: 2,
          questionText: "Circuit safety precaution",
          topic: "precautions",
          difficulty: "beginner",
          studentAnswer: "Be careful",
          evaluation: {
            verdict: "incorrect",
            score: 2,
            whatYouGotRight: "Mentioned care",
            whatWasMissing: "Switch off power supply",
            expectedAnswer: "Always open the key when circuit is idle",
            improvementTip: "Mention the plug key",
            providerMode: "demonstration",
          },
          timestamp: Date.now() - 4200,
        },
      ],
      totalQuestions: 5,
      questionsAnswered: 2,
      correctCount: 1,
      partiallyCorrectCount: 0,
      incorrectCount: 1,
      averageScore: 6.0,
      topicAnalysis: {},
      weakTopics: ["precautions"],
      strongTopics: ["theory"],
      revisionRecommendations: [
        {
          topic: "Safety Precautions",
          reason: "Questions on circuit safety precautions received lower scores.",
          suggestedAction: "Review safety warnings in the Precautions tab.",
          workspaceTab: "precautions",
        },
      ],
      providerMode: "demonstration",
    },
  ];

  const metrics = calculateOverviewMetrics(mockExp, mockSessions, "all");
  assert.strictEqual(metrics.totalExperiments, 1);
  assert.strictEqual(metrics.vivaSessionsCount, 2);
  assert.strictEqual(metrics.completedVivaSessionsCount, 1);
  // Average score must be 6.0 (only from the completed session, not the incomplete 2.0!)
  assert.strictEqual(metrics.averageVivaScore, 6.0);
  // Preparation percentage: 2 out of 5 items checked = 40%
  assert.strictEqual(metrics.preparationPercentage, 40);

  const readiness = calculateExperimentReadiness(mockExp, mockSessions);
  assert.strictEqual(readiness[0].readinessStatus, "in-progress");
  assert.strictEqual(readiness[0].completedChecklistCount, 2);
  assert.strictEqual(readiness[0].latestVivaScore, 6.0);

  const topics = aggregateTopicPerformance(mockSessions, "all");
  const theoryTopic = topics.find((t) => t.topicKey === "theory");
  const precautionsTopic = topics.find((t) => t.topicKey === "precautions");
  assert.strictEqual(theoryTopic.questionsAnswered, 1);
  assert.strictEqual(theoryTopic.averageScore, 10.0);
  assert.strictEqual(precautionsTopic.questionsAnswered, 1);
  assert.strictEqual(precautionsTopic.averageScore, 2.0);
  assert.strictEqual(precautionsTopic.status, "needs-revision");

  const priorities = extractRevisionPriorities(mockSessions, mockExp);
  assert.strictEqual(priorities.length, 1);
  assert.strictEqual(priorities[0].topic, "Safety Precautions");
  assert.strictEqual(priorities[0].workspaceTab, "precautions");

  console.log("✓ Test Case 2 Passed: Incomplete sessions excluded, checklist & topic scores verified");
}

// Test Case 3: Dangling Sessions for Deleted Experiments
{
  const remainingExperiments = [
    {
      id: "exp_active",
      title: "Diffraction Grating",
      subject: "Physics",
      status: "ready",
      createdAt: "2026-10-01",
      createdAtTimestamp: 1000,
      updatedAt: "2026-10-01",
      updatedAtTimestamp: 1000,
      vivaQuestionsCount: 5,
    },
  ];

  const pastSessions = [
    {
      id: "sess_deleted_exp",
      experimentId: "exp_deleted_999",
      experimentTitle: "Deleted Lab Manual",
      subject: "Chemistry",
      config: { questionCount: 5, difficulty: "intermediate", focus: "theory" },
      startedAt: Date.now() - 50000,
      completedAt: Date.now() - 40000,
      isCompleted: true,
      answers: [],
      totalQuestions: 5,
      questionsAnswered: 5,
      correctCount: 1,
      partiallyCorrectCount: 0,
      incorrectCount: 4,
      averageScore: 3.0,
      topicAnalysis: {},
      weakTopics: ["theory"],
      strongTopics: [],
      revisionRecommendations: [
        {
          topic: "Titration Curve",
          reason: "Missed inflection points",
          suggestedAction: "Study reaction kinetics",
          workspaceTab: "theory",
        },
      ],
      providerMode: "demonstration",
    },
  ];

  // Priorities must omit recommendations for deleted experiments so no dead links are rendered
  const priorities = extractRevisionPriorities(pastSessions, remainingExperiments);
  assert.strictEqual(priorities.length, 0);
  console.log("✓ Test Case 3 Passed: Deleted experiments do not create dangling revision links");
}

// Test Case 4: Period Filtering (7d, 30d, all)
{
  const now = Date.now();
  const testSessions = [
    {
      id: "s_today",
      experimentId: "e1",
      experimentTitle: "E1",
      subject: "S",
      config: { questionCount: 5, difficulty: "beginner", focus: "mixed" },
      startedAt: now - 3600000, // 1 hour ago
      completedAt: now - 3500000,
      isCompleted: true,
      answers: [],
      totalQuestions: 5,
      questionsAnswered: 5,
      correctCount: 5,
      partiallyCorrectCount: 0,
      incorrectCount: 0,
      averageScore: 9.0,
      topicAnalysis: {},
      weakTopics: [],
      strongTopics: [],
      revisionRecommendations: [],
      providerMode: "demonstration",
    },
    {
      id: "s_15d",
      experimentId: "e1",
      experimentTitle: "E1",
      subject: "S",
      config: { questionCount: 5, difficulty: "beginner", focus: "mixed" },
      startedAt: now - 15 * 86400000, // 15 days ago
      completedAt: now - 15 * 86400000 + 1000,
      isCompleted: true,
      answers: [],
      totalQuestions: 5,
      questionsAnswered: 5,
      correctCount: 3,
      partiallyCorrectCount: 1,
      incorrectCount: 1,
      averageScore: 6.0,
      topicAnalysis: {},
      weakTopics: [],
      strongTopics: [],
      revisionRecommendations: [],
      providerMode: "demonstration",
    },
    {
      id: "s_45d",
      experimentId: "e1",
      experimentTitle: "E1",
      subject: "S",
      config: { questionCount: 5, difficulty: "beginner", focus: "mixed" },
      startedAt: now - 45 * 86400000, // 45 days ago
      completedAt: now - 45 * 86400000 + 1000,
      isCompleted: true,
      answers: [],
      totalQuestions: 5,
      questionsAnswered: 5,
      correctCount: 1,
      partiallyCorrectCount: 1,
      incorrectCount: 3,
      averageScore: 4.0,
      topicAnalysis: {},
      weakTopics: [],
      strongTopics: [],
      revisionRecommendations: [],
      providerMode: "demonstration",
    },
  ];

  const allFiltered = filterSessionsByPeriod(testSessions, "all");
  assert.strictEqual(allFiltered.length, 3);

  const thirtyDayFiltered = filterSessionsByPeriod(testSessions, "30d");
  assert.strictEqual(thirtyDayFiltered.length, 2);
  assert.strictEqual(thirtyDayFiltered.map((s) => s.id).includes("s_45d"), false);

  const sevenDayFiltered = filterSessionsByPeriod(testSessions, "7d");
  assert.strictEqual(sevenDayFiltered.length, 1);
  assert.strictEqual(sevenDayFiltered[0].id, "s_today");

  console.log("✓ Test Case 4 Passed: 7d, 30d, and all-time reporting periods accurately filter records");
}

console.log("\nALL 4 TEST SUITES PASSED CLEANLY!");
