"""unique constraint na identitet prijave + dedup postojećih duplikata

Revision ID: a7e1c3b9d402
Revises: 9220ae9d2154
Create Date: 2026-04-22 13:30:00.000000

Sprečava dupliranje prijava kada roditelj brzo klikne "Pošalji" dva puta
(race condition koji se dešavao pri burst-u zahteva pod Passenger queue-om).

Zbog MySQL InnoDB key prefix limita (767 bajta na starijim verzijama,
3072 na 8.0+) koristimo prefiks od 50 znakova za name/surname kolone —
praktično dovoljno za jedinstvenost, sigurno ispod svih MySQL limita.

Pre nego što se kreira indeks, migracija briše postojeće duplikate
(zadržava najstariji red po id-u za svaku grupu istih identiteta).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7e1c3b9d402'
down_revision = '9220ae9d2154'
branch_labels = None
depends_on = None


DEDUP_SQL = """
DELETE a1 FROM application AS a1
INNER JOIN application AS a2
  ON a1.id > a2.id
 AND a1.children_name    = a2.children_name
 AND a1.children_surname = a2.children_surname
 AND a1.mother_name      = a2.mother_name
 AND a1.mother_surname   = a2.mother_surname
 AND a1.father_name      = a2.father_name
 AND a1.father_surname   = a2.father_surname
 AND a1.grade            = a2.grade
 AND a1.class_number     = a2.class_number
"""


CREATE_INDEX_SQL = """
CREATE UNIQUE INDEX uq_application_identity ON application (
    children_name(50),
    children_surname(50),
    mother_name(50),
    mother_surname(50),
    father_name(50),
    father_surname(50),
    grade,
    class_number
)
"""


def upgrade():
    conn = op.get_bind()
    # 1) obriši postojeće duplikate (zadržavamo najstariji red)
    result = conn.execute(sa.text(DEDUP_SQL))
    if hasattr(result, 'rowcount') and result.rowcount is not None:
        print(f"[migration] Obrisano duplikata: {result.rowcount}")

    # 2) kreiraj unique prefix indeks (raw SQL zbog column prefix-a)
    conn.execute(sa.text(CREATE_INDEX_SQL))


def downgrade():
    op.drop_index('uq_application_identity', table_name='application')
