import datetime

def get_time_details():
    now = datetime.datetime.now()

    # Day of the week (0 = Monday, 6 = Sunday)
    day_of_week = now.weekday()  # 0 = Monday, 6 = Sunday

    # Week of the year
    week_of_year = now.strftime("%U")

    # Month of the year
    month_of_year = now.month  # Numeric month (1 = January, 12 = December)

    # Quarter of the year (1 = Q1, 4 = Q4)
    quarter_of_year = (now.month - 1) // 3 + 1

    # Current year
    year = now.year

    return {
        "Day": day_of_week,
        "Week": week_of_year,
        "Month": month_of_year,
        "Quarter": quarter_of_year,
        "Year": year
    }

