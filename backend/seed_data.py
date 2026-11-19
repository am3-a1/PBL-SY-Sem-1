from datetime import datetime, timedelta
import random

RAW_SEED_REVIEWS = [
    # --- Login Crash ---
    {
        "source": "App Store",
        "author": "TechEnthusiast99",
        "rating": 1,
        "content": "Since updating to version 4.2.0 yesterday, the app crashes immediately on the splash screen! I can't even get to the login form. Running iOS 17.4 on iPhone 15 Pro.",
        "days_ago": 1,
    },
    {
        "source": "Google Play",
        "author": "Marcus Brody",
        "rating": 1,
        "content": "Continuous crash loop on Android 14. Tried clearing cache, re-installing, and rebooting. As soon as I type my password and tap Login, it shuts down.",
        "days_ago": 2,
    },
    {
        "source": "Reddit",
        "author": "u/pixel_dev_23",
        "rating": None,
        "content": "Is anyone else experiencing instantaneous force closes when trying to authenticate with Google OAuth? Works on web but the mobile app died completely after the latest patch.",
        "days_ago": 2,
    },
    {
        "source": "Discord",
        "author": "AlexV#9012",
        "rating": None,
        "content": "Hey @support, the Face ID login is completely broken. Prompt pops up, scans face, then screen turns black and application crashes back to home screen.",
        "days_ago": 3,
    },
    {
        "source": "App Store",
        "author": "Sarah Jenkins",
        "rating": 1,
        "content": "Terrible! I have an urgent client deadline and the 2FA SMS code never arrives. When I tap 'Resend OTP' the app freezes and crashes. Please fix ASAP!",
        "days_ago": 3,
    },
    {
        "source": "Google Play",
        "author": "David K.",
        "rating": 1,
        "content": "Keeps crashing upon login. Error message flashes for 0.1 seconds before exiting to home. Totally unusable right now.",
        "days_ago": 4,
    },
    {
        "source": "Reddit",
        "author": "u/ios_tester_girl",
        "rating": 2,
        "content": "Login session expires every 20 minutes and logging back in fails with 'Network Error 502'. Very frustrating user experience.",
        "days_ago": 5,
    },
    {
        "source": "Discord",
        "author": "GhostRider#4412",
        "rating": None,
        "content": "Can confirm login crash on Pixel 8 Pro. Clean install doesn't fix it. Logcat shows NullPointerException in AuthProvider.",
        "days_ago": 5,
    },
    {
        "source": "App Store",
        "author": "Brian_C",
        "rating": 1,
        "content": "Updated the app this morning and now it won't let me sign in. It just spins forever on 'Authenticating credentials' and then force closes.",
        "days_ago": 6,
    },
    {
        "source": "Google Play",
        "author": "Elena Rostova",
        "rating": 2,
        "content": "Fingerprint scanner login causes the entire phone to lag and the app freezes on black screen. Password login works fine though.",
        "days_ago": 7,
    },
    {
        "source": "Discord",
        "author": "NeonVibe#1101",
        "rating": None,
        "content": "Is login server down? When clicking submit on auth form nothing happens. Then app crashes after 30 seconds timeout.",
        "days_ago": 8,
    },
    {
        "source": "Reddit",
        "author": "u/coder_guy99",
        "rating": 1,
        "content": "Massive bug in auth workflow: reset password link in email leads to a 404 page inside the webview which triggers an uncaught crash.",
        "days_ago": 9,
    },
    {
        "source": "App Store",
        "author": "Chloe_M",
        "rating": 1,
        "content": "Cannot log in using Apple ID anymore. Says 'Authorization canceled' even though I approved it. Can't access my paid features!",
        "days_ago": 10,
    },

    # --- Billing & Payments ---
    {
        "source": "App Store",
        "author": "Jessica Miller",
        "rating": 1,
        "content": "You charged my credit card twice for the annual subscription ($89.99 x 2) and your in-app restore purchase button says 'No active license found'!",
        "days_ago": 1,
    },
    {
        "source": "Google Play",
        "author": "Carlos Gomez",
        "rating": 1,
        "content": "Canceled my Pro trial 3 days before it ended, yet Google Play still charged me $14.99! Requesting refund immediately.",
        "days_ago": 2,
    },
    {
        "source": "Reddit",
        "author": "u/finance_hawk",
        "rating": None,
        "content": "PSA: Check your credit card statements if you use FeedPulse/this app. I was billed for a renewal after explicitly canceling in settings.",
        "days_ago": 3,
    },
    {
        "source": "Discord",
        "author": "CryptoKing#8834",
        "rating": None,
        "content": "Payment gateway declined my Mastercard three times with cryptic error 0x44B. Support hasn't answered my ticket in 48 hours.",
        "days_ago": 4,
    },
    {
        "source": "App Store",
        "author": "Amanda B.",
        "rating": 2,
        "content": "The pricing structure changed without notification. Was paying $4.99/mo and suddenly got an invoice for $12.99. Very dishonest.",
        "days_ago": 5,
    },
    {
        "source": "Google Play",
        "author": "Tariq Al-Mansoor",
        "rating": 1,
        "content": "Paid for the lifetime license upgrade. Transaction went through on bank, but app still locks features behind the upgrade paywall.",
        "days_ago": 6,
    },
    {
        "source": "Reddit",
        "author": "u/angry_subscriber",
        "rating": 1,
        "content": "Billing support is virtually nonexistent. Bot answers with generic links and nobody handles refund requests.",
        "days_ago": 7,
    },
    {
        "source": "Discord",
        "author": "ZoeS#2020",
        "rating": None,
        "content": "Why is there no option to remove saved payment methods? This feels like a huge GDPR compliance violation.",
        "days_ago": 8,
    },
    {
        "source": "App Store",
        "author": "Kenneth P.",
        "rating": 3,
        "content": "Good app overall, but the billing page is very confusing. It doesn't clearly display when the renewal date is.",
        "days_ago": 9,
    },
    {
        "source": "Google Play",
        "author": "Sven Lindqvist",
        "rating": 2,
        "content": "Currency conversion on checkout charged in USD instead of EUR with a hefty foreign exchange fee. Please add local currency support.",
        "days_ago": 11,
    },
    {
        "source": "Reddit",
        "author": "u/saas_auditor",
        "rating": None,
        "content": "Warning to team accounts: adding an additional member automatically charged an annual seat with zero confirmation modal or prorated calculation.",
        "days_ago": 12,
    },
    {
        "source": "App Store",
        "author": "Natalie K",
        "rating": 1,
        "content": "My subscription lapsed due to an expired card. I updated card details, payment cleared, but my account is still marked 'Suspended'.",
        "days_ago": 13,
    },

    # --- Performance & Lag ---
    {
        "source": "Google Play",
        "author": "Devin Wright",
        "rating": 1,
        "content": "My phone gets burning hot within 5 minutes of using this app. Battery drained 25% in half an hour. Unbelievable memory leak.",
        "days_ago": 1,
    },
    {
        "source": "App Store",
        "author": "Alex_G",
        "rating": 2,
        "content": "Stutters constantly when scrolling through tables or feeds. Drops from 120hz ProMotion down to what feels like 15 fps. Very laggy.",
        "days_ago": 2,
    },
    {
        "source": "Reddit",
        "author": "u/sysadmin_bench",
        "rating": None,
        "content": "Did some profiling on the latest build. Memory consumption climbs from 180MB to 1.4GB after opening 5 tabs. Huge RAM leak somewhere in image caching.",
        "days_ago": 3,
    },
    {
        "source": "Discord",
        "author": "SpeedDemon#0077",
        "rating": None,
        "content": "API responses take 4-6 seconds to load simple metric cards. Is the backend server throttled or database queries unindexed?",
        "days_ago": 4,
    },
    {
        "source": "Google Play",
        "author": "Priya Sharma",
        "rating": 2,
        "content": "Extremely sluggish on Samsung Galaxy S23. Typing into search bar has a 1-second keyboard latency delay. Please optimize performance.",
        "days_ago": 5,
    },
    {
        "source": "App Store",
        "author": "Oli_Q",
        "rating": 2,
        "content": "App takes 12 seconds to boot from cold start on iPhone 13. Competitor apps open in under 2 seconds.",
        "days_ago": 6,
    },
    {
        "source": "Discord",
        "author": "VaporWave#3341",
        "rating": None,
        "content": "Massive battery drain on iOS background sync. Battery settings report 48% background usage overnight while idle.",
        "days_ago": 7,
    },
    {
        "source": "Reddit",
        "author": "u/fps_counter",
        "rating": 2,
        "content": "Scrolling animation is horribly janky on Android 13. UI thread is clearly being blocked by background data parsing.",
        "days_ago": 8,
    },
    {
        "source": "Google Play",
        "author": "Lucas Silva",
        "rating": 3,
        "content": "Great features but noticeably laggy when handling projects with more than 50 items. Needs better virtualization.",
        "days_ago": 10,
    },
    {
        "source": "App Store",
        "author": "Emma_W",
        "rating": 2,
        "content": "The phone gets so hot I have to put it down. Please fix the CPU utilization in the chart rendering modules.",
        "days_ago": 12,
    },
    {
        "source": "Discord",
        "author": "Hyperion#1984",
        "rating": None,
        "content": "High latency when switching between dashboard views. Sometimes shows empty white card for 3 seconds before rendering.",
        "days_ago": 14,
    },

    # --- UI/UX ---
    {
        "source": "App Store",
        "author": "GraphicDan",
        "rating": 2,
        "content": "The new redesign is terrible. Fonts are tiny, contrast is awful in dark mode, and important buttons got hidden inside nested submenus.",
        "days_ago": 1,
    },
    {
        "source": "Reddit",
        "author": "u/ux_purist",
        "rating": None,
        "content": "Why did they replace the clean bottom tab bar with an awkward hamburger drawer? Now everything takes 2 extra taps to reach.",
        "days_ago": 2,
    },
    {
        "source": "Google Play",
        "author": "Fiona_G",
        "rating": 3,
        "content": "UI looks sleek at first glance but is unintuitive. Accidentally archive items all the time because swipe gesture threshold is too sensitive.",
        "days_ago": 3,
    },
    {
        "source": "Discord",
        "author": "DesignLover#5521",
        "rating": None,
        "content": "Dark mode contrast is unreadable under sunlight. Gray text #71717A on #18181B background violates WCAG AA accessibility standards.",
        "days_ago": 4,
    },
    {
        "source": "App Store",
        "author": "Matthew Taylor",
        "rating": 3,
        "content": "The layout is cramped on smaller iPhone screens (SE 3rd Gen). Modal headers overlap the close button.",
        "days_ago": 6,
    },
    {
        "source": "Google Play",
        "author": "Aisha Khan",
        "rating": 4,
        "content": "Really like the color palette and modern aesthetic. Just wish there was an option to customize toolbar icons.",
        "days_ago": 7,
    },
    {
        "source": "Reddit",
        "author": "u/minimalist_vibes",
        "rating": 4,
        "content": "Unpopular opinion: I actually enjoy the new minimalist design. Less clutter, cleaner typography, and nice rounded pill tags.",
        "days_ago": 8,
    },
    {
        "source": "Discord",
        "author": "CyberPunk#4040",
        "rating": None,
        "content": "Can we get custom themes or an OLED black mode? The dark gray is nice but pure black would save battery on AMOLED.",
        "days_ago": 9,
    },
    {
        "source": "App Store",
        "author": "Rachel_G",
        "rating": 3,
        "content": "Drag and drop on iPad works great with Apple Pencil, but on phone it's clumsy and hard to target columns.",
        "days_ago": 11,
    },
    {
        "source": "Google Play",
        "author": "Dmitry Ivanov",
        "rating": 3,
        "content": "Filters dropdown menu closes every time you select a single checkbox. Should let us select multiple tags before closing.",
        "days_ago": 13,
    },
    {
        "source": "Reddit",
        "author": "u/product_lead_dan",
        "rating": None,
        "content": "Feedback on Kanban board: card heights are inconsistent when reviews are long. Adding an expand/collapse toggle would clean up the view.",
        "days_ago": 15,
    },

    # --- General (Positive & Feature Requests & Neutral) ---
    {
        "source": "App Store",
        "author": "Samantha Reed",
        "rating": 5,
        "content": "FeedPulse has completely transformed how our product team triages user reviews! Love the automated sentiment scores and Slack integration.",
        "days_ago": 1,
    },
    {
        "source": "Google Play",
        "author": "Hiroshi Tanaka",
        "rating": 5,
        "content": "Best feedback management tool we've used this year. Ingesting both Google Play and Reddit discussions in one unified board is a game changer.",
        "days_ago": 2,
    },
    {
        "source": "Reddit",
        "author": "u/startup_founder_99",
        "rating": 5,
        "content": "Huge shoutout to the devs! We connected our customer channels and caught a major payment bug within 10 minutes of release. Highly recommended.",
        "days_ago": 2,
    },
    {
        "source": "Discord",
        "author": "ApexBuilder#1337",
        "rating": None,
        "content": "The mock data generator and CSV import pipeline make onboarding seamless. Clean code, rock solid backend architecture.",
        "days_ago": 3,
    },
    {
        "source": "App Store",
        "author": "Jen_A",
        "rating": 5,
        "content": "Five stars! The analytics charts give our stakeholders instant visibility into sentiment health. Fast, responsive, and intuitive.",
        "days_ago": 4,
    },
    {
        "source": "Google Play",
        "author": "Mateo Rossi",
        "rating": 5,
        "content": "Extremely smooth workflow. Being able to drag items straight into 'Escalated to Engineering' saves our support reps hours every week.",
        "days_ago": 5,
    },
    {
        "source": "Reddit",
        "author": "u/growth_marketer",
        "rating": 4,
        "content": "Solid MVP. Would love to see email digest reports and export to Jira/Linear in upcoming versions. Overall super happy.",
        "days_ago": 6,
    },
    {
        "source": "Discord",
        "author": "PixelForge#2048",
        "rating": None,
        "content": "Great tool guys. Fast local NLP processing without needing OpenAI API keys is such a breath of fresh air.",
        "days_ago": 7,
    },
    {
        "source": "App Store",
        "author": "Chris_N",
        "rating": 4,
        "content": "Really impressed with how accurately it clusters login crash complaints versus normal UI remarks. Good job team.",
        "days_ago": 8,
    },
    {
        "source": "Google Play",
        "author": "Fatima Zahra",
        "rating": 5,
        "content": "Super helpful tool! Very simple to upload our weekly customer survey CSV and see instant sentiment trends.",
        "days_ago": 9,
    },
    {
        "source": "Discord",
        "author": "Starlight#7711",
        "rating": None,
        "content": "The Slack alert notification is so well formatted! The Block Kit layout shows exactly what went wrong without clicking around.",
        "days_ago": 10,
    },
    {
        "source": "Reddit",
        "author": "u/devops_ninja",
        "rating": 4,
        "content": "Zero configuration SQLite backend makes local deployment trivial. Clean separation of concerns between NLP and API layers.",
        "days_ago": 12,
    },
    {
        "source": "App Store",
        "author": "Ben_F",
        "rating": 5,
        "content": "Outstanding release. Our weekly churn rate dropped because we resolve critical login errors before they spiral out of control.",
        "days_ago": 14,
    },
    {
        "source": "Google Play",
        "author": "Dev_Grace",
        "rating": 4,
        "content": "Works reliably on all devices. Would be great to have webhook support for Microsoft Teams as well in future updates.",
        "days_ago": 16,
    },
    {
        "source": "Discord",
        "author": "EchoWave#9900",
        "rating": None,
        "content": "Just tested the triage board with our 20k Discord member server. Community team loves how clear the card statuses are.",
        "days_ago": 18,
    },
    {
        "source": "App Store",
        "author": "Tom_H",
        "rating": 4,
        "content": "Reliable and fast. The dark mode theme is easy on the eyes during late night customer triage shifts.",
        "days_ago": 20,
    },
    {
        "source": "Google Play",
        "author": "Sophie Martin",
        "rating": 5,
        "content": "Brilliant product. Saves so much manual tagging and spreadsheet work. Essential utility for modern agile squads.",
        "days_ago": 22,
    },
    {
        "source": "Reddit",
        "author": "u/open_source_hero",
        "rating": 5,
        "content": "Kudos for using VADER and scikit-learn! No latency from external LLM rate limits and works completely offline.",
        "days_ago": 25,
    },
]


def generate_seed_reviews():
    """
    Returns a list of structured review dictionaries ready for insertion into the database.
    """
    now = datetime.utcnow()
    initial_statuses = ["New", "Investigating", "Escalated", "Resolved"]
    # Realistic distribution: negative reviews more likely in New or Escalated, positive in Resolved or New
    results = []

    for item in RAW_SEED_REVIEWS:
        created_time = now - timedelta(days=item.get("days_ago", 1), hours=random.randint(1, 23), minutes=random.randint(0, 59))
        
        # Determine realistic initial status
        if item.get("rating") == 1:
            status = random.choice(["New", "Investigating", "Escalated"])
        elif item.get("rating") == 5:
            status = random.choice(["Resolved", "New"])
        else:
            status = random.choice(initial_statuses)

        results.append({
            "source": item["source"],
            "author": item["author"],
            "rating": item.get("rating"),
            "content": item["content"],
            "created_at": created_time,
            "status": status,
        })

    return results
