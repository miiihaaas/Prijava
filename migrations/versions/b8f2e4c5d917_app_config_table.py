"""app_config tabela za admin-podesivi datum otvaranja prijava

Revision ID: b8f2e4c5d917
Revises: a7e1c3b9d402
Create Date: 2026-04-22 14:00:00.000000

Dodaje singleton tabelu sa jednim poljem application_open_date, koje admin
postavlja kroz /admin/settings. Pre ovog datuma, / renderuje countdown a
/application redirektuje na /. Ako je polje NULL, prijave su otvorene
(backward compatible).
"""
from alembic import op
import sqlalchemy as sa


revision = 'b8f2e4c5d917'
down_revision = 'a7e1c3b9d402'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'app_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('application_open_date', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('app_config')
