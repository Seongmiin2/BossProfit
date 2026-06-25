from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("profit", "0005_dailymenusale"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("category", models.CharField(max_length=50)),
                ("region", models.CharField(default="전국", max_length=100)),
                ("unit", models.CharField(max_length=30)),
                ("image_key", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="MarketPriceObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("observed_date", models.DateField()),
                ("price", models.DecimalField(decimal_places=2, max_digits=14)),
                ("volume", models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ("source", models.CharField(max_length=100)),
                ("collected_at", models.DateTimeField()),
                ("is_demo", models.BooleanField(default=False)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="observations", to="profit.marketitem")),
            ],
            options={"ordering": ["-observed_date", "-collected_at"]},
        ),
        migrations.CreateModel(
            name="MarketForecast",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("as_of_date", models.DateField()),
                ("target_date", models.DateField()),
                ("horizon_days", models.PositiveSmallIntegerField()),
                ("predicted_price", models.DecimalField(decimal_places=2, max_digits=14)),
                ("lower_price", models.DecimalField(decimal_places=2, max_digits=14)),
                ("upper_price", models.DecimalField(decimal_places=2, max_digits=14)),
                ("expected_change_rate", models.DecimalField(decimal_places=4, max_digits=8)),
                ("confidence_grade", models.CharField(default="검증 전", max_length=20)),
                ("model_version", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_demo", models.BooleanField(default=False)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forecasts", to="profit.marketitem")),
            ],
            options={"ordering": ["horizon_days", "-as_of_date"]},
        ),
        migrations.CreateModel(
            name="MarketModelMetric",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("model_version", models.CharField(max_length=100)),
                ("horizon_days", models.PositiveSmallIntegerField()),
                ("direction_accuracy", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ("wape", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ("interval_coverage", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ("evaluation_start", models.DateField(blank=True, null=True)),
                ("evaluation_end", models.DateField(blank=True, null=True)),
                ("is_verified", models.BooleanField(default=False)),
                ("item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="model_metrics", to="profit.marketitem")),
            ],
        ),
        migrations.CreateModel(
            name="MarketRecommendation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("as_of_date", models.DateField()),
                ("decision", models.CharField(choices=[("BUY", "미리 구매 검토"), ("WATCH", "관망"), ("AVOID", "구매 보류")], max_length=20)),
                ("summary", models.TextField()),
                ("action", models.TextField()),
                ("evidence", models.JSONField(default=list)),
                ("is_demo", models.BooleanField(default=False)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recommendations", to="profit.marketitem")),
            ],
            options={"ordering": ["-as_of_date"]},
        ),
        migrations.CreateModel(
            name="MarketRankingSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ranking_type", models.CharField(choices=[("VOLUME", "거래량"), ("TODAY", "오늘 가격 변동"), ("TOMORROW", "내일 예상 변동")], max_length=20)),
                ("as_of_date", models.DateField()),
                ("rank", models.PositiveSmallIntegerField()),
                ("previous_rank", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("score", models.DecimalField(decimal_places=4, max_digits=14)),
                ("display_change_rate", models.DecimalField(decimal_places=4, max_digits=8)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                ("is_demo", models.BooleanField(default=False)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ranking_snapshots", to="profit.marketitem")),
            ],
            options={"ordering": ["ranking_type", "as_of_date", "rank"]},
        ),
        migrations.AddConstraint(
            model_name="marketpriceobservation",
            constraint=models.UniqueConstraint(fields=("item", "observed_date", "source"), name="unique_market_observation"),
        ),
        migrations.AddConstraint(
            model_name="marketforecast",
            constraint=models.UniqueConstraint(fields=("item", "as_of_date", "horizon_days", "model_version"), name="unique_market_forecast"),
        ),
        migrations.AddConstraint(
            model_name="marketmodelmetric",
            constraint=models.UniqueConstraint(fields=("item", "model_version", "horizon_days"), name="unique_market_model_metric"),
        ),
        migrations.AddConstraint(
            model_name="marketrecommendation",
            constraint=models.UniqueConstraint(fields=("item", "as_of_date"), name="unique_market_recommendation"),
        ),
        migrations.AddConstraint(
            model_name="marketrankingsnapshot",
            constraint=models.UniqueConstraint(fields=("ranking_type", "as_of_date", "rank"), name="unique_market_ranking_position"),
        ),
        migrations.AddConstraint(
            model_name="marketrankingsnapshot",
            constraint=models.UniqueConstraint(fields=("ranking_type", "as_of_date", "item"), name="unique_market_ranking_item"),
        ),
    ]
