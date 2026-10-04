# Cross Continental Swim Race Analytics 13 Years, 27000+ Swimmer

- **Boğaziçi Kıtalararası Yüzme Yarışı** (Istanbul 6500 m) results from 2014 to 2026
- **Çanakkale Boğaz Yüzme Yarışması** (Çanakkale 5000 m) results from 2026

---

## 1. Participation Boğaziçi Kıtalararası Yüzme Yarışı 2014-2026

![Participation over years by gender](./output/participation_over_years_by_gender.png)

**Findings**

- Total finishers grew from 1647 in 2014 to a peak of 2666 in 2025 rise of about 62%.
- 2016 and 2020 show sharp drops. The 2020 drop lines up with the global pandemic.
- 2026 shows a drop from the 2025 peak, down to 2336 finishers (about -12%).

---

## 2. Overall position vs finish time by sex

![Overall position vs time by gender](./output/overall_position_vs_time_by_sex.png)

**Findings**

- Each years curve follows similar shape 1) slow rise through the fast group 2) flat middle section then 3) steep rise at the tail.
- Curves with the longest tail (2024, 2025) match the years with the highest total finisher counts.

---

## 3. 2026 cross race comparison: Çanakkale vs Istanbul

### 3.1 Pace relationship between two races

![Çanakkale vs Istanbul common pace](./2026/output/canakkale_vs_istanbul_common_pace.png)

**Findings**

- 455 athletes finished both races in 2026
- Pace in one race predicts pace in the other: Pearson r = 0.836 (R^2 = 0.70).
- Rank order is even more stable than pace: Spearman $\rho$ = 0.870.
- Median pace in Çanakkale is 81.4 s/100m. Median pace in Istanbul is 72.0 s/100m. The gap is 9.4 s/100m.
- Istanbul course runs faster for almost every swimmer in the shared group that means much stronger current than the Çanakkale course.

### 3.2 Pace by age group both races

![Age group Kruskal-Wallis](./2026/output/age_group_kruskal_wallis.png)

**Findings**

- The Kruskal-Wallis test returns p < 0.01 in all four panels (male/female x Çanakkale/Istanbul). Age group has a real effect on pace in both races.
- The effect is stronger for men (H = 48.4 Çanakkale, H = 42.2 Istanbul) than for women (H = 24.6 Çanakkale, H = 26.0 Istanbul).
- Pace is fastest in the 19-29 age range and slows from the 60+ groups onward in both races.
- Istanbul pace is faster than Çanakkale pace in every age group.

---

## 4. Istanbul 2026 full race breakdown

### 4.1 Finish-time distribution

![Istanbul finish time distribution](./2026/istanbul/output/01_finish_time_distribution.png)

**Findings**

- 2208 finishers median time 1:18:20
- Top 5% finished under 1:03:17 top 10% finished under 1:07:03
- The distribution is right skewed with a long tail past 1:40:00
- My own time 1:11:40 close to the top 25% line

### 4.2 Finish time by age band and gender

![Istanbul age band and gender](./2026/istanbul/output/02_age_group_gender.png)

**Findings**

- The 14-18 age band posts the fastest median time for both sexes

### 4.3 Participation and gender split by nation

![Istanbul nation participation](./2026/istanbul/output/04_nation_gender_participation.png)

**Findings**

- Türkiye has 1474 of 2336 finishers about 63% of the field.
- Russia is the second largest group with 278 finishers then Great Britain, Ukraine and the US.
- Female share by nation varies widely 60% in the UAE, near 50% in the Netherlands and Kazakhstan but under 15% in Georgia and Uzbekistan.

### 4.4 Finish time density, male vs. female

![Istanbul gender KDE](./2026/istanbul/output/05_gender_kde.png)

**Findings**

- male median: 1:17:23 (n = 1621), female median: 1:21:58 (n = 587), gap: 275 seconds

---

## 5. Çanakkale 2026 - full race breakdown

### 5.1 Finish-time distribution

![Çanakkale finish time distribution](./2026/canakkale/output/01_finish_time_distribution.png)

**Findings**

- 1318 finishers median time: 1:13:02
- Top 5% finished under 55:19. Top 10% finished under 59:40.
- Histogram shows two density regions. First and the main peak sits near 1:08:00 to 1:15:00 around the median. Second one is smaller peak that sits near 1:28:00 to 1:35:00. This pattern points competitive swimmers in the first peak, recreational swimmers in the second peak.
- My own time 59:20 falls 10% mark (59:40) this places the result inside the top decile of the field.

### 5.2 Finish time by age band and gender

![Çanakkale age band and gender](./2026/canakkale/output/02_age_group_gender.png)

**Findings**

- As in Istanbul the 14-18 age band posts the fastest median for both sexes.

### 5.3 Participation and median pace by nation

![Çanakkale nation participation and pace](./2026/canakkale/output/04_nation_participation_pace.png)

**Findings**

- Türkiye has 1073 of 1536 finishers about 70% of the field
- The field drops off sharply after Türkiye, Great Britain 81, Russia 44 and United States 29.
- The fastest median pace by nation belongs to Australia (1:19/100m) ahead of the US and Guernsey (1:21/100m each).

### 5.4 Finish-time density male vs female

![Çanakkale gender KDE](./2026/canakkale/output/05_gender_kde.png)

**Findings**

- Male median: 1:11:11 (n = 859), female median: 1:17:22 (n = 459), gap: 371 seconds (larger than the 275 second gap in Istanbul)
- The female distribution again runs wider and further right than the male distribution.

---

## Methods notes

- Finish times include only official, valid results (status = FINISHED).
- Gender labels come from official race registration data.
- The Kruskal-Wallis H test checks whether pace distributions differ across age groups. A low p-value (< 0.05) rejects the claim that all groups share the same distribution.
- Pearson r measures the linear fit between two pace series. Spearman ρ measures how well rank order carries over independent of a linear fit.
- Small sub-groups (n < 10) appear in several charts. Treat their medians as indicative, not conclusive.

---

## How to reproduce

```bash
pip install -r requirements.txt
python participation_over_years.py
python overall_position_vs_time.py
python 2026/common_2026_charts.py
python 2026/istanbul/visualize_results.py
python 2026/canakkale/visualize_results.py
```

Each script writes its charts to the matching `output/` folder shown in the repository structure above.