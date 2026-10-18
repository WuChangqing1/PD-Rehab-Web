"""Add native number allocations without rewriting any patient or foreign key."""
import re
from alembic import op
import sqlalchemy as sa

revision='i5d7e9f1a3b4'
down_revision='h4c6d8e0f2a3'
branch_labels=None
depends_on=None


def upgrade():
    table=op.create_table('patient_number_allocations',
        sa.Column('id',sa.BigInteger().with_variant(sa.Integer(),'sqlite'),primary_key=True,autoincrement=True),
        sqlite_autoincrement=True)
    # Read only the existing identifiers, including deleted records. No renumbering.
    highest=0
    for number in op.get_bind().execute(sa.text('SELECT hospital_number FROM patients')).scalars():
        matched=re.fullmatch(r'P([0-9]+)',number)
        if matched:
            value=int(matched[1])
            if 0<value<2**63-1:highest=max(highest,value)
    if highest:op.bulk_insert(table,[{'id':highest}])


def downgrade():
    op.drop_table('patient_number_allocations')
