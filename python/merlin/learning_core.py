

class LearnerStore:
    """SQLite persistence for attempts and dimension-specific mastery evidence."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    learner_id TEXT NOT NULL,
                    lesson_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    scores_json TEXT NOT NULL,
                    independent INTEGER NOT NULL,
                    hints_used INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS mastery (
                    learner_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    estimate REAL NOT NULL CHECK (estimate >= 0 AND estimate <= 1),
                    evidence_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (learner_id, concept_id, dimension)
                );
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_attempt(
        self,
        attempt: Attempt,
        concept_ids: Sequence[str],
        *,
        learning_rate: float = 0.35,
    ) -> int:
        """Persist one validated learner attempt and update mastery atomically."""
        if not isinstance(attempt, Attempt):
            raise TypeError("attempt must be an Attempt")
        for field_name in ("learner_id", "lesson_id", "task_id"):
            value = getattr(attempt, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if isinstance(learning_rate, bool) or not isinstance(learning_rate, (int, float)):
            raise ValueError("learning_rate must be a finite number in (0, 1]")
        learning_rate = float(learning_rate)
        if not math.isfinite(learning_rate) or not 0 < learning_rate <= 1:
            raise ValueError("learning_rate must be a finite number in (0, 1]")
        if not isinstance(attempt.independent, bool):
            raise ValueError("independent must be boolean")
        if isinstance(attempt.hints_used, bool) or not isinstance(attempt.hints_used, int) or attempt.hints_used < 0:
            raise ValueError("hints_used must be a non-negative integer")
        if not isinstance(attempt.outcome, str) or not attempt.outcome.strip():
            raise ValueError("outcome must be a non-empty string")
        if not isinstance(attempt.scores, Mapping) or not attempt.scores:
            raise ValueError("at least one mastery dimension must be assessed")
        unknown = set(attempt.scores) - set(MASTERY_DIMENSIONS)
        if unknown:
            raise ValueError(f"unknown mastery dimensions: {sorted(unknown)}")
        normalized_scores: dict[str, float] = {}
        for dimension, raw_score in attempt.scores.items():
            if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
                raise ValueError(f"{dimension} score must be a finite number between 0 and 1")
            score = float(raw_score)
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError(f"{dimension} score must be a finite number between 0 and 1")
            normalized_scores[dimension] = score
        if not isinstance(attempt.evidence, Mapping):
            raise ValueError("evidence must be a mapping")
        try:
            scores_json = json.dumps(normalized_scores, sort_keys=True, allow_nan=False)
            evidence_json = json.dumps(dict(attempt.evidence), sort_keys=True, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("attempt evidence must be finite JSON-serializable data") from exc
        if isinstance(concept_ids, (str, bytes)) or not isinstance(concept_ids, Sequence) or not concept_ids:
            raise ValueError("concept_ids must be a non-empty sequence of identifiers")
        if any(not isinstance(item, str) or not item.strip() for item in concept_ids):
            raise ValueError("concept identifiers must be non-empty strings")
        unique_concepts = tuple(sorted(set(concept_ids)))

        evidence_weight = 1.0 if attempt.independent and attempt.hints_used == 0 else 0.75
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO attempts
                (learner_id, lesson_id, task_id, scores_json, independent,
                 hints_used, outcome, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    attempt.learner_id.strip(), attempt.lesson_id.strip(), attempt.task_id.strip(),
                    scores_json, int(attempt.independent), attempt.hints_used, attempt.outcome.strip(),
                    evidence_json,
                ),
            )
            attempt_id = int(cursor.lastrowid)
            for concept_id in unique_concepts:
                for dimension, raw_score in normalized_scores.items():
                    score = raw_score * evidence_weight
                    row = connection.execute(
                        """SELECT estimate, evidence_count FROM mastery
                        WHERE learner_id=? AND concept_id=? AND dimension=?""",
                        (attempt.learner_id.strip(), concept_id, dimension),
                    ).fetchone()
                    previous = float(row["estimate"]) if row else 0.0
                    count = int(row["evidence_count"]) if row else 0
                    estimate = previous + learning_rate * (score - previous)
                    connection.execute(
                        """INSERT INTO mastery
                        (learner_id, concept_id, dimension, estimate, evidence_count)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(learner_id, concept_id, dimension)
                        DO UPDATE SET estimate=excluded.estimate,
                                      evidence_count=excluded.evidence_count,
                                      updated_at=CURRENT_TIMESTAMP""",
                        (attempt.learner_id.strip(), concept_id, dimension, estimate, count + 1),
                    )
            return attempt_id

    def mastery(self, learner_id: str, concept_id: str) -> dict[str, float]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT dimension, estimate FROM mastery WHERE learner_id=? AND concept_id=?",
                (learner_id, concept_id),
            ).fetchall()
        result = {dimension: 0.0 for dimension in MASTERY_DIMENSIONS}
        result.update({row["dimension"]: float(row["estimate"]) for row in rows})
        return result

    def attempt_count(self, learner_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM attempts WHERE learner_id=?", (learner_id,)
            ).fetchone()
        return int(row["count"])


def select_next_lesson(
    learner_id: str,
    store: LearnerStore,
    lessons: Sequence[LessonSpec],
    concepts: ConceptRegistry = DEFAULT_CONCEPTS,
    *,
    path: str = "mathematician",
    mastery_threshold: float = 0.70,
) -> LessonSpec | None:
    """Select the highest-priority eligible lesson; zero-history learners start at zero."""
    concepts.validate()
    eligible: list[tuple[float, str, LessonSpec]] = []
    for lesson in lessons:
        lesson.validate()
        if path not in lesson.path_tags:
            continue
        known_concepts = {concept.concept_id for concept in concepts.all()}
        unknown_concepts = (set(lesson.target_concepts) | set(lesson.prerequisites)) - known_concepts
        if unknown_concepts:
            raise ValueError(
                f"lesson {lesson.lesson_id} references unknown concepts: {sorted(unknown_concepts)}"
            )
        if any(
            sum(
                store.mastery(learner_id, prerequisite)[dimension]
                for dimension in ("conceptual", "procedural", "representational")
            ) / 3.0 < mastery_threshold
            for prerequisite in lesson.prerequisites
        ):
            continue
        gap = sum(
            1.0 - sum(store.mastery(learner_id, concept).values()) / len(MASTERY_DIMENSIONS)
            for concept in lesson.target_concepts
        )
        score = lesson.priority + gap
        eligible.append((score, lesson.lesson_id, lesson))
    if not eligible:
        return None
    eligible.sort(key=lambda item: (-item[0], item[1]))
    return eligible[0][2]


# --- Spaced repetition, comprehensive input, and strategy-mix experiments ---
