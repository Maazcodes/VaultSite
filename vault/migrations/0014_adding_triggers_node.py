from django.db import migrations
from django.conf import settings
from django.contrib.postgres.operations import CreateExtension

import vault.ltree


def get_sql(filename):
    with open(settings.BASE_DIR / "vault/sql" / filename) as f:
        return f.read()


class Migration(migrations.Migration):

    dependencies = [
        ("vault", "0013_creating_node"),
    ]

    operations = [
        # Add the 'ltree' extension to PostgreSQL. Only needed once.
        CreateExtension("ltree"),
        # Add the 'path' field to the TreeNode model
        migrations.AddField(
            model_name="TreeNode",
            name="path",
            field=vault.ltree.LtreeField(editable=False, null=True, default=None),
        ),
        # Create some indexes
        migrations.RunSQL(get_sql("index.sql")),
        # Add a constraint for recursivity
        migrations.RunSQL(get_sql("constraint.sql")),
        # Add a PostgreSQL trigger to manage the path automatically
        migrations.RunSQL(get_sql("triggers.sql")),
    ]
