# Generated by Django 4.2.20 on 2025-04-25 22:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('playground', '0003_rootcauseanalysis_failure_category_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rootcauseanalysis',
            name='affected_components',
            field=models.JSONField(blank=True, default=list, help_text='List of system components affected by this failure', null=True),
        ),
        migrations.AddField(
            model_name='rootcauseanalysis',
            name='last_updated',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='rootcauseanalysis',
            name='confidence',
            field=models.CharField(choices=[('HIGH', 'High - Strong evidence with high certainty'), ('MEDIUM', 'Medium - Reasonable evidence but some uncertainty'), ('LOW', 'Low - Limited evidence with significant uncertainty')], help_text='Confidence level in the accuracy of this analysis', max_length=10),
        ),
        migrations.AlterField(
            model_name='rootcauseanalysis',
            name='detailed_analysis',
            field=models.TextField(help_text='In-depth explanation of the failure and its causes'),
        ),
        migrations.AlterField(
            model_name='rootcauseanalysis',
            name='failure_category',
            field=models.CharField(blank=True, help_text="General category of failure (e.g., 'API Validation', 'Authentication', 'Database')", max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='rootcauseanalysis',
            name='impact_severity',
            field=models.CharField(choices=[('CRITICAL', 'Critical - Service outage or data loss'), ('HIGH', 'High - Major functionality impaired'), ('MEDIUM', 'Medium - Limited functionality impact'), ('LOW', 'Low - Minor or cosmetic issues')], default='MEDIUM', help_text='Severity of the impact this failure would have in production', max_length=10),
        ),
        migrations.AlterField(
            model_name='rootcauseanalysis',
            name='potential_solutions',
            field=models.TextField(help_text='Recommended actions to address the root cause'),
        ),
        migrations.AlterField(
            model_name='rootcauseanalysis',
            name='root_cause',
            field=models.TextField(help_text='Brief summary of the primary root cause identified'),
        ),
        migrations.AlterField(
            model_name='rootcauseanalysis',
            name='tags',
            field=models.JSONField(blank=True, default=list, help_text='Tags for filtering and grouping RCAs', null=True),
        ),
        migrations.AlterField(
            model_name='rootcauseanalysis',
            name='time_to_detect_ms',
            field=models.IntegerField(default=0, help_text='Time taken to detect the failure in milliseconds'),
        ),
        migrations.AddIndex(
            model_name='rootcauseanalysis',
            index=models.Index(fields=['failure_category'], name='playground__failure_789105_idx'),
        ),
        migrations.AddIndex(
            model_name='rootcauseanalysis',
            index=models.Index(fields=['impact_severity'], name='playground__impact__d0ba6e_idx'),
        ),
        migrations.AddIndex(
            model_name='rootcauseanalysis',
            index=models.Index(fields=['confidence'], name='playground__confide_8e1311_idx'),
        ),
    ]
