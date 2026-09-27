"""Seed data for the News & Updates feed.

Ported verbatim from ``gst-app/src/pages/NewsAndUpdates.jsx`` (NEWS_DATA)
so the portal serves exactly what the UI used to hardcode.
"""

NEWS_ITEMS = [
    # ── 2026 ──────────────────────────────────────────────────────────
    {
        "news_type": "Notification",
        "published_date": "Jan 15, 2026",
        "year": 2026,
        "month": 1,
        "featured": True,
        "title": "GSTR-3B late fee waiver extended till 31st March 2026",
        "summary": "CBIC Notification No. 03/2026 – Central Tax dated 14.01.2026 extends the waiver of late fee for delayed filing of FORM GSTR-3B for specified taxpayers.",  # noqa: E501
        "tag": "Returns",
        "pdf_available": True,
    },
    {
        "news_type": "Revenue Update",
        "published_date": "Jan 12, 2026",
        "year": 2026,
        "month": 1,
        "featured": True,
        "title": "Gross GST revenue for December 2025 crosses ₹1.78 lakh crore",
        "summary": "Net collection after refunds stands at ₹1.52 lakh crore. MoM growth 7.8%, YoY growth 11.4%. Detailed state-wise breakup and sector analysis released.",  # noqa: E501
        "tag": "Others",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Jan 8, 2026",
        "year": 2026,
        "month": 1,
        "featured": False,
        "title": "Advisory on IMS (Invoice Management System) for taxpayers",
        "summary": "GSTN has issued an advisory for taxpayers on the new Invoice Management System enabling real-time reconciliation of invoices between suppliers and recipients.",  # noqa: E501
        "tag": "ITC",
        "pdf_available": False,
    },
    {
        "news_type": "Advisory",
        "published_date": "Jan 3, 2026",
        "year": 2026,
        "month": 1,
        "featured": False,
        "title": "Mandatory e-invoicing for taxpayers with AATO above ₹5 crore",
        "summary": "E-invoicing is now mandatory for all registered taxpayers with aggregate annual turnover exceeding ₹5 crore from 1st February 2026 onwards.",  # noqa: E501
        "tag": "E-Invoice",
        "pdf_available": True,
    },
    # ── 2025 ──────────────────────────────────────────────────────────
    {
        "news_type": "Circular",
        "published_date": "Dec 28, 2025",
        "year": 2025,
        "month": 12,
        "featured": False,
        "title": "Clarification on ITC eligibility for construction services",
        "summary": "CBIC Circular No. 226/20/2025-GST clarifies the scope of ITC eligibility for works contract and construction services under Section 17(5) of CGST Act.",  # noqa: E501
        "tag": "ITC",
        "pdf_available": True,
    },
    {
        "news_type": "Update",
        "published_date": "Dec 22, 2025",
        "year": 2025,
        "month": 12,
        "featured": False,
        "title": "GSTN portal update: New reconciliation tool for GSTR-2B vs books",
        "summary": "GSTN launched an upgraded reconciliation module that allows taxpayers to directly match GSTR-2B auto-drafted ITC with purchase register data.",  # noqa: E501
        "tag": "Portal",
        "pdf_available": False,
    },
    {
        "news_type": "Press Release",
        "published_date": "Dec 18, 2025",
        "year": 2025,
        "month": 12,
        "featured": False,
        "title": "GST Council 55th meeting outcomes – key decisions summary",
        "summary": "The 55th GST Council meeting chaired by Finance Minister concluded with several significant recommendations including rate rationalisation and compliance relief.",  # noqa: E501
        "tag": "Council",
        "pdf_available": True,
    },
    {
        "news_type": "Notification",
        "published_date": "Dec 10, 2025",
        "year": 2025,
        "month": 12,
        "featured": False,
        "title": "CGST Rules amended – new provisions for GSTR-9 annual return",
        "summary": "Central Tax notification amends CGST Rules 2017 to include new disclosure requirements in GSTR-9 for FY 2024-25 onwards. HSN-wise reporting mandatory.",  # noqa: E501
        "tag": "Returns",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Nov 20, 2025",
        "year": 2025,
        "month": 11,
        "featured": False,
        "title": "Advisory on E-Way Bill generation for multi-vehicle transport",
        "summary": "GSTN issues guidance on generating consolidated E-Way Bills for consignments transported via multiple vehicles in a single dispatch cycle.",  # noqa: E501
        "tag": "E-Way Bill",
        "pdf_available": False,
    },
    {
        "news_type": "Revenue Update",
        "published_date": "Nov 5, 2025",
        "year": 2025,
        "month": 11,
        "featured": False,
        "title": "GST revenue for October 2025 stands at ₹1.87 lakh crore",
        "summary": "October 2025 marks a new record with ₹1.87 lakh crore gross GST collection driven by strong domestic consumption and improved compliance metrics.",  # noqa: E501
        "tag": "Revenue",
        "pdf_available": True,
    },
    {
        "news_type": "Circular",
        "published_date": "Oct 14, 2025",
        "year": 2025,
        "month": 10,
        "featured": False,
        "title": "Circular on reversal of ITC on credit notes from supplier",
        "summary": "CBIC clarifies the mechanism for reversal of ITC availed on credit notes issued by suppliers under Rule 37A of CGST Rules 2017.",  # noqa: E501
        "tag": "ITC",
        "pdf_available": True,
    },
    {
        "news_type": "Notification",
        "published_date": "Oct 2, 2025",
        "year": 2025,
        "month": 10,
        "featured": False,
        "title": "Extension of due date for GSTR-1 for September 2025",
        "summary": "CBIC extends the due date for filing GSTR-1 for the month of September 2025 by 5 days due to technical glitches reported on the GSTN portal.",  # noqa: E501
        "tag": "Returns",
        "pdf_available": False,
    },
    {
        "news_type": "Update",
        "published_date": "Sep 18, 2025",
        "year": 2025,
        "month": 9,
        "featured": False,
        "title": "GSTN launches new taxpayer dashboard with compliance score",
        "summary": "The revamped GSTN dashboard introduces a Compliance Rating Score for each registered taxpayer based on timely filing, payment, and ITC matching.",  # noqa: E501
        "tag": "Portal",
        "pdf_available": False,
    },
    {
        "news_type": "Press Release",
        "published_date": "Sep 3, 2025",
        "year": 2025,
        "month": 9,
        "featured": False,
        "title": "MoF releases GST collection data for Q1 FY 2025-26",
        "summary": "Ministry of Finance data shows Q1 FY26 total GST revenue at ₹5.57 lakh crore, reflecting 13.2% growth over corresponding period of previous financial year.",  # noqa: E501
        "tag": "Revenue",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Aug 22, 2025",
        "year": 2025,
        "month": 8,
        "featured": False,
        "title": "Advisory on new Table 14 and Table 15 in GSTR-1",
        "summary": "GSTN issues advisory explaining new reporting requirements for supplies through e-commerce operators in the revised GSTR-1 format effective September 2025.",  # noqa: E501
        "tag": "Returns",
        "pdf_available": True,
    },
    {
        "news_type": "Circular",
        "published_date": "Aug 8, 2025",
        "year": 2025,
        "month": 8,
        "featured": False,
        "title": "Clarification on export of services under IGST Act Section 2(6)",
        "summary": "CBIC Circular 225/2025 clarifies conditions under which IT and consulting services provided to foreign clients qualify as export of services with zero-rated status.",  # noqa: E501
        "tag": "Exports",
        "pdf_available": True,
    },
    # ── 2024 ──────────────────────────────────────────────────────────
    {
        "news_type": "Notification",
        "published_date": "Dec 12, 2024",
        "year": 2024,
        "month": 12,
        "featured": False,
        "title": "CBIC notifies reduced GST rate on health insurance premiums",
        "summary": "GST rate on individual health insurance policies with sum insured up to ₹5 lakh reduced from 18% to 5% effective 1st January 2025 as per Council decision.",  # noqa: E501
        "tag": "Rates",
        "pdf_available": True,
    },
    {
        "news_type": "Revenue Update",
        "published_date": "Dec 2, 2024",
        "year": 2024,
        "month": 12,
        "featured": False,
        "title": "November 2024 GST collections cross ₹1.82 lakh crore mark",
        "summary": "Festive season spending and improved compliance drove November 2024 GST collections to ₹1.82 lakh crore, a 9.4% year-on-year increase.",  # noqa: E501
        "tag": "Revenue",
        "pdf_available": False,
    },
    {
        "news_type": "Advisory",
        "published_date": "Oct 25, 2024",
        "year": 2024,
        "month": 10,
        "featured": False,
        "title": "GSTN advisory on GSTR-2B generation delay for October 2024",
        "summary": "GSTN acknowledges a technical issue causing delay in GSTR-2B generation for October 2024 and advises taxpayers to wait before filing GSTR-3B.",  # noqa: E501
        "tag": "ITC",
        "pdf_available": False,
    },
    {
        "news_type": "Circular",
        "published_date": "Oct 10, 2024",
        "year": 2024,
        "month": 10,
        "featured": False,
        "title": "Place of supply rules clarification for cloud computing services",
        "summary": "CBIC issues detailed circular on determining place of supply for cloud, SaaS, and hosted software services under Schedule II of IGST Act.",  # noqa: E501
        "tag": "IGST",
        "pdf_available": True,
    },
    {
        "news_type": "Press Release",
        "published_date": "Aug 20, 2024",
        "year": 2024,
        "month": 8,
        "featured": False,
        "title": "GST Council 54th meeting: Rate rationalisation on cancer drugs",
        "summary": "54th GST Council recommends reduction of GST rate on three cancer treatment drugs to 5% and exemption for satellite-based broadband internet services.",  # noqa: E501
        "tag": "Council",
        "pdf_available": True,
    },
    {
        "news_type": "Update",
        "published_date": "Aug 5, 2024",
        "year": 2024,
        "month": 8,
        "featured": False,
        "title": "New HSN search tool launched on GST portal for taxpayers",
        "summary": "GSTN introduces an AI-powered HSN search functionality on the GST portal allowing taxpayers to identify correct HSN codes by entering product descriptions.",  # noqa: E501
        "tag": "Portal",
        "pdf_available": False,
    },
    {
        "news_type": "Notification",
        "published_date": "Jun 14, 2024",
        "year": 2024,
        "month": 6,
        "featured": False,
        "title": "Amnesty scheme for pending GST appeals announced",
        "summary": "CBIC announces a one-time amnesty scheme for taxpayers with pending GST demands under Section 128A allowing settlement without interest and penalty.",  # noqa: E501
        "tag": "Compliance",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Jun 3, 2024",
        "year": 2024,
        "month": 6,
        "featured": False,
        "title": "Advisory on reporting of intra-state supplies in GSTR-3B",
        "summary": "Taxpayers advised to correctly segregate intra-state B2B, B2C, and exempt supplies in respective tables of GSTR-3B to avoid mismatch notices.",  # noqa: E501
        "tag": "Returns",
        "pdf_available": True,
    },
    # ── 2023 ──────────────────────────────────────────────────────────
    {
        "news_type": "Revenue Update",
        "published_date": "Dec 5, 2023",
        "year": 2023,
        "month": 12,
        "featured": False,
        "title": "FY 2023-24 GST collections show consistent growth above ₹1.6 lakh crore",
        "summary": "Eight consecutive months of collections above ₹1.6 lakh crore reflect structural improvement in compliance driven by e-invoicing and portal automation.",  # noqa: E501
        "tag": "Revenue",
        "pdf_available": True,
    },
    {
        "news_type": "Circular",
        "published_date": "Dec 1, 2023",
        "year": 2023,
        "month": 12,
        "featured": False,
        "title": "Circular on valuation of corporate guarantee between related parties",
        "summary": "CBIC Circular 204/2023 prescribes a 1% of the guaranteed amount as the taxable value of corporate guarantees extended between related persons under GST.",  # noqa: E501
        "tag": "Valuation",
        "pdf_available": True,
    },
    {
        "news_type": "Notification",
        "published_date": "Sep 18, 2023",
        "year": 2023,
        "month": 9,
        "featured": False,
        "title": "E-invoicing threshold reduced to ₹5 crore AATO",
        "summary": "CBIC notification mandates e-invoicing for all taxpayers with aggregate annual turnover exceeding ₹5 crore from 1st August 2023.",  # noqa: E501
        "tag": "E-Invoice",
        "pdf_available": True,
    },
    {
        "news_type": "Update",
        "published_date": "Sep 2, 2023",
        "year": 2023,
        "month": 9,
        "featured": False,
        "title": "GSTN enables biometric Aadhaar authentication for new GST registration",
        "summary": "New GST registrations in Gujarat and Andhra Pradesh now require biometric Aadhaar authentication at GST Suvidha Kendras as an anti-fraud measure.",  # noqa: E501
        "tag": "Registration",
        "pdf_available": False,
    },
    {
        "news_type": "Press Release",
        "published_date": "Jun 12, 2023",
        "year": 2023,
        "month": 6,
        "featured": False,
        "title": "50th GST Council meeting – milestone decisions and special session",
        "summary": "The 50th GST Council meeting held in New Delhi recommended GST on online gaming at 28% on full face value and concluded review of inverted duty structure.",  # noqa: E501
        "tag": "Council",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Jun 1, 2023",
        "year": 2023,
        "month": 6,
        "featured": False,
        "title": "Advisory on availment of ITC on demo vehicles by automobile dealers",
        "summary": "GSTN clarifies that GST paid on purchase of demo vehicles used by automobile dealers for business demonstration is eligible as input tax credit.",  # noqa: E501
        "tag": "ITC",
        "pdf_available": True,
    },
    # ── 2022 ──────────────────────────────────────────────────────────
    {
        "news_type": "Notification",
        "published_date": "Nov 28, 2022",
        "year": 2022,
        "month": 11,
        "featured": False,
        "title": "CGST Rules amended to implement mandatory ITC reversal mechanism",
        "summary": "Rule 37A inserted in CGST Rules to provide automated ITC reversal and reclaim mechanism for GSTR-2B based ITC where supplier fails to pay tax.",  # noqa: E501
        "tag": "ITC",
        "pdf_available": True,
    },
    {
        "news_type": "Revenue Update",
        "published_date": "Nov 3, 2022",
        "year": 2022,
        "month": 11,
        "featured": False,
        "title": "October 2022 GST revenue at ₹1.52 lakh crore – 2nd highest ever",
        "summary": "October 2022 GST collections at ₹1,51,718 crore, the second highest since GST implementation, driven by economic recovery and festive season demand.",  # noqa: E501
        "tag": "Revenue",
        "pdf_available": False,
    },
    {
        "news_type": "Circular",
        "published_date": "Aug 3, 2022",
        "year": 2022,
        "month": 8,
        "featured": False,
        "title": "Clarification on GST treatment of transactions in crypto assets",
        "summary": "CBIC issues guidance on GST applicability on transfer of virtual digital assets, clarifying that brokerage and exchange fees attract 18% GST.",  # noqa: E501
        "tag": "Digital",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Aug 1, 2022",
        "year": 2022,
        "month": 8,
        "featured": False,
        "title": "GSTN advisory on the new Annual Return GSTR-9 for FY 2021-22",
        "summary": "Advisory explains key changes in GSTR-9 and GSTR-9C for FY 2021-22 including optional reporting of HSN details and reconciliation statement changes.",  # noqa: E501
        "tag": "Returns",
        "pdf_available": True,
    },
    {
        "news_type": "Update",
        "published_date": "Apr 20, 2022",
        "year": 2022,
        "month": 4,
        "featured": False,
        "title": "GST portal launches automated GSTR-1 filing assistance tool",
        "summary": "A new GSTR-1 filing assistant tool on the GST portal pre-populates invoice data from IRP reducing manual entry errors and improving filing accuracy.",  # noqa: E501
        "tag": "Portal",
        "pdf_available": False,
    },
    {
        "news_type": "Press Release",
        "published_date": "Apr 4, 2022",
        "year": 2022,
        "month": 4,
        "featured": False,
        "title": "GST revenue in March 2022 at ₹1.42 lakh crore – all-time high then",
        "summary": "March 2022 GST collection of ₹1,42,095 crore sets a new record driven by year-end compliance push and improved e-invoicing adoption across sectors.",  # noqa: E501
        "tag": "Revenue",
        "pdf_available": True,
    },
    # ── 2021 ──────────────────────────────────────────────────────────
    {
        "news_type": "Notification",
        "published_date": "Dec 21, 2021",
        "year": 2021,
        "month": 12,
        "featured": False,
        "title": "Auto-population of GSTR-3B from GSTR-1 and GSTR-2B enabled",
        "summary": "GSTN enables Phase-I of auto-population of liability and ITC values in GSTR-3B based on filed GSTR-1 and system-generated GSTR-2B for all taxpayers.",  # noqa: E501
        "tag": "Returns",
        "pdf_available": True,
    },
    {
        "news_type": "Circular",
        "published_date": "Dec 8, 2021",
        "year": 2021,
        "month": 12,
        "featured": False,
        "title": "Clarification on GST on employee secondment – overseas entities",
        "summary": "CBIC Circular 167/2021 clarifies that services by overseas holding company employees seconded to Indian subsidiaries attract GST under reverse charge.",  # noqa: E501
        "tag": "RCM",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Sep 12, 2021",
        "year": 2021,
        "month": 9,
        "featured": False,
        "title": "Advisory on introduction of GSTR-2B for ITC reconciliation",
        "summary": "GSTN introduces GSTR-2B as a static ITC statement to facilitate accurate reconciliation and reduce ITC mismatches between buyers and suppliers.",  # noqa: E501
        "tag": "ITC",
        "pdf_available": False,
    },
    {
        "news_type": "Revenue Update",
        "published_date": "Sep 1, 2021",
        "year": 2021,
        "month": 9,
        "featured": False,
        "title": "August 2021 GST revenue crosses ₹1.12 lakh crore post-pandemic recovery",
        "summary": "GST collections in August 2021 at ₹1,12,020 crore reflect strong recovery from COVID-19 disruptions with all major states showing double-digit growth.",  # noqa: E501
        "tag": "Revenue",
        "pdf_available": False,
    },
    # ── 2020 ──────────────────────────────────────────────────────────
    {
        "news_type": "Notification",
        "published_date": "Oct 1, 2020",
        "year": 2020,
        "month": 10,
        "featured": False,
        "title": "QRMP scheme introduced for small taxpayers with turnover up to ₹5 crore",
        "summary": "CBIC introduces Quarterly Return Monthly Payment (QRMP) scheme allowing eligible taxpayers to file GSTR-1 and GSTR-3B on quarterly basis from January 2021.",  # noqa: E501
        "tag": "Compliance",
        "pdf_available": True,
    },
    {
        "news_type": "Circular",
        "published_date": "Oct 15, 2020",
        "year": 2020,
        "month": 10,
        "featured": False,
        "title": "Circular clarifying ITC restriction on employee welfare expenses",
        "summary": "CBIC Circular 172/2020 clarifies restrictions on ITC availment on canteen, health insurance, and other employee welfare expenses under Section 17(5).",  # noqa: E501
        "tag": "ITC",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Apr 3, 2020",
        "year": 2020,
        "month": 4,
        "featured": False,
        "title": "Advisory on COVID-19 GST compliance relief – due date extensions",
        "summary": "GSTN issues advisory on relief measures for taxpayers during COVID-19 pandemic including waiver of late fees and extension of return filing due dates.",  # noqa: E501
        "tag": "Compliance",
        "pdf_available": False,
    },
    {
        "news_type": "Update",
        "published_date": "Apr 1, 2020",
        "year": 2020,
        "month": 4,
        "featured": False,
        "title": "GST portal enhancements for bulk filing and offline tool update",
        "summary": "Updated GSTR-1 and GSTR-3B offline tools released with improved performance for bulk invoice upload and error-handling for large taxpayers.",  # noqa: E501
        "tag": "Portal",
        "pdf_available": False,
    },
    # ── 2019 ──────────────────────────────────────────────────────────
    {
        "news_type": "Notification",
        "published_date": "Dec 26, 2019",
        "year": 2019,
        "month": 12,
        "featured": False,
        "title": "E-invoicing scheme notified – implementation from April 2020",
        "summary": "CBIC notifies e-invoicing under Rule 48(4) of CGST Rules for taxpayers with AATO exceeding ₹500 crore to be implemented from 1st April 2020.",  # noqa: E501
        "tag": "E-Invoice",
        "pdf_available": True,
    },
    {
        "news_type": "Revenue Update",
        "published_date": "Dec 3, 2019",
        "year": 2019,
        "month": 12,
        "featured": False,
        "title": "GST collections for November 2019 show month-on-month improvement",
        "summary": "November 2019 GST revenue at ₹1,03,492 crore improves over previous months reflecting government initiatives to improve return filing compliance rates.",  # noqa: E501
        "tag": "Revenue",
        "pdf_available": False,
    },
    {
        "news_type": "Circular",
        "published_date": "Aug 14, 2019",
        "year": 2019,
        "month": 8,
        "featured": False,
        "title": "Circular on GST applicability on educational services and institutions",
        "summary": "CBIC Circular 151/2019 comprehensively clarifies exemption scope for educational services including coaching classes, online courses, and exam fees.",  # noqa: E501
        "tag": "Exemption",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Aug 2, 2019",
        "year": 2019,
        "month": 8,
        "featured": False,
        "title": "Advisory on Composition Scheme annual return CMP-08 for FY 2018-19",
        "summary": "GSTN issues advisory on filing of annual statement CMP-08 for composition dealers for FY 2018-19 with step-by-step guidance on portal navigation.",  # noqa: E501
        "tag": "Composition",
        "pdf_available": False,
    },
    # ── 2018 ──────────────────────────────────────────────────────────
    {
        "news_type": "Notification",
        "published_date": "Nov 15, 2018",
        "year": 2018,
        "month": 11,
        "featured": False,
        "title": "GST rates revised downward on 28 goods at 32nd Council meeting",
        "summary": "32nd GST Council meeting reduces rates on several items including TV sets up to 32 inches, computer monitors, lithium-ion batteries, and handmade goods.",  # noqa: E501
        "tag": "Rates",
        "pdf_available": True,
    },
    {
        "news_type": "Circular",
        "published_date": "Nov 2, 2018",
        "year": 2018,
        "month": 11,
        "featured": False,
        "title": "Circular on treatment of secondary discounts and post-sale incentives",
        "summary": "CBIC Circular 105/2018 clarifies GST implications of trade discounts, volume incentives, and other post-sale incentives between distributors and manufacturers.",  # noqa: E501
        "tag": "Valuation",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "May 18, 2018",
        "year": 2018,
        "month": 5,
        "featured": False,
        "title": "Advisory on the new return filing system – GST 2.0 pilot",
        "summary": "GSTN issues advisory on the pilot launch of the new simplified return filing system featuring SAHAJ, SUGAM, and main return formats for different taxpayer categories.",  # noqa: E501
        "tag": "Returns",
        "pdf_available": False,
    },
    {
        "news_type": "Update",
        "published_date": "May 4, 2018",
        "year": 2018,
        "month": 5,
        "featured": False,
        "title": "E-Way Bill system fully operational across all states",
        "summary": "E-Way Bill system becomes operational for inter-state and intra-state movement of goods across all 29 states and 7 union territories from April and May 2018.",  # noqa: E501
        "tag": "E-Way Bill",
        "pdf_available": False,
    },
    # ── 2017 ──────────────────────────────────────────────────────────
    {
        "news_type": "Notification",
        "published_date": "Jul 1, 2017",
        "year": 2017,
        "month": 7,
        "featured": True,
        "title": "GST officially launched – historic tax reform comes into effect",
        "summary": "Goods and Services Tax replaces multiple indirect taxes including Central Excise, VAT, and Service Tax from midnight of 1st July 2017 with a unified structure.",  # noqa: E501
        "tag": "Launch",
        "pdf_available": True,
    },
    {
        "news_type": "Advisory",
        "published_date": "Jul 15, 2017",
        "year": 2017,
        "month": 7,
        "featured": False,
        "title": "GSTN advisory on first-time registration and migration from VAT to GST",
        "summary": "Comprehensive advisory for businesses migrating from VAT, Service Tax, and Central Excise to the new GST regime including provisional ID and ARN guidance.",  # noqa: E501
        "tag": "Registration",
        "pdf_available": True,
    },
    {
        "news_type": "Circular",
        "published_date": "Sep 25, 2017",
        "year": 2017,
        "month": 9,
        "featured": False,
        "title": "Clarification on transitional credit under Section 140 of CGST Act",
        "summary": "CBIC Circular 1/2017 clarifies the procedure for availing of transitional credit of pre-GST taxes like CENVAT and VAT in TRAN-1 and TRAN-2 forms.",  # noqa: E501
        "tag": "Transition",
        "pdf_available": True,
    },
    {
        "news_type": "Revenue Update",
        "published_date": "Sep 1, 2017",
        "year": 2017,
        "month": 9,
        "featured": False,
        "title": "First GST revenue data – ₹92,283 crore collected in July 2017",
        "summary": "Government releases first GST collection data for July 2017 showing ₹92,283 crore from 72.5 lakh returns filed, with CGST, SGST, and IGST breakup.",  # noqa: E501
        "tag": "Revenue",
        "pdf_available": False,
    },
]
