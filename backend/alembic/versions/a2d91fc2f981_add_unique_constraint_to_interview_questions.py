"""add_unique_constraint_to_interview_questions

Revision ID: a2d91fc2f981
Revises: 9a3f9a7e2d1b
Create Date: 2026-04-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a2d91fc2f981"
down_revision: Union[str, Sequence[str], None] = "9a3f9a7e2d1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONSTRAINT_NAME = "uq_interview_questions_interview_id_question_text"


def upgrade() -> None:
    """Deduplicate historic rows and add hard uniqueness guard."""
    op.execute(
        """
        WITH ranked AS (
            SELECT
                ctid,
                ROW_NUMBER() OVER (
                    PARTITION BY interview_id, question_text
                    ORDER BY id
                ) AS rn
            FROM interview_questions
        )
        DELETE FROM interview_questions q
        USING ranked r
        WHERE q.ctid = r.ctid
          AND r.rn > 1;
        """
    )

    op.create_unique_constraint(
        CONSTRAINT_NAME,
        "interview_questions",
        ["interview_id", "question_text"],
    )


def downgrade() -> None:
    """Remove hard uniqueness guard."""
    op.drop_constraint(CONSTRAINT_NAME, "interview_questions", type_="unique")
