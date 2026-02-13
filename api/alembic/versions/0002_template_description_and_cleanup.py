"""add template description column and remove stale duplicate

Revision ID: 0002_template_desc
Revises: 0001_initial
Create Date: 2026-02-13 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_template_desc"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("templates", sa.Column("description", sa.String(length=500), nullable=True))

  # Remove stale duplicate of "Turbulence and Snacks" (see TESTING_FINDINGS.md item #3).
  op.execute("DELETE FROM templates WHERE id = 't-unexpected-plane-vacation-mini'")

  # Prevent future title duplicates.
  op.create_unique_constraint("uq_templates_title", "templates", ["title"])


def downgrade() -> None:
  op.drop_constraint("uq_templates_title", "templates", type_="unique")
  op.drop_column("templates", "description")
