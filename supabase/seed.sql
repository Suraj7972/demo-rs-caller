-- =============================================================================
-- Demo seed: 1 builder org, 1 broker org (channel partner), 2 Pune projects,
-- visit slots, and project_access so the broker can sell both projects.
-- All names, RERA numbers, phone numbers and URLs are FICTIONAL demo data.
-- Idempotent: safe to run more than once.
-- =============================================================================

-- ------------------------------------------------------------------ orgs ----
insert into public.orgs (id, name, type, plan, minutes_quota) values
  ('11111111-1111-4111-8111-111111111111', 'Sahyadri Realty (Demo)',     'builder', 'pilot', 3000),
  ('22222222-2222-4222-8222-222222222222', 'PuneHomes Advisors (Demo)',  'broker',  'pilot', 1500)
on conflict (id) do nothing;

-- ---------------------------------------------- Project 1: Hinjewadi ------
insert into public.projects (id, org_id, builder_name, name, location, rera_no, config) values (
  'aaaaaaaa-0000-4000-8000-000000000001',
  '11111111-1111-4111-8111-111111111111',
  'Sahyadri Realty',
  'Sahyadri Greens',
  'Hinjewadi Phase 2, Pune',
  'P52100099901',
  $json${
    "company_display_name": {"en": "Sahyadri Realty", "hi": "सह्याद्री रियल्टी", "mr": "सह्याद्री रिअल्टी"},
    "project_display_name": {"en": "Sahyadri Greens", "hi": "सह्याद्री ग्रीन्स", "mr": "सह्याद्री ग्रीन्स"},
    "tagline": "Township living next to the Rajiv Gandhi Infotech Park",
    "bhk_types": [
      {"type": "1BHK", "carpet_sqft": [450, 520],  "price_inr": [5800000, 6500000]},
      {"type": "2BHK", "carpet_sqft": [680, 760],  "price_inr": [7800000, 9200000]},
      {"type": "3BHK", "carpet_sqft": [980, 1080], "price_inr": [11500000, 13000000]}
    ],
    "price_note": "Prices are all-inclusive of GST and parking; stamp duty and registration are extra.",
    "payment_plans": ["Construction-linked plan (CLP)"],
    "towers": 6,
    "floors": "G+22",
    "total_units": 840,
    "land_acres": 7.5,
    "amenities": [
      "Clubhouse with gym", "Swimming pool", "Kids play area", "Jogging track",
      "Indoor games room", "Co-working lounge", "EV charging points", "24x7 security with CCTV",
      "Rainwater harvesting", "Solar-powered common areas"
    ],
    "possession": {"target_date": "2027-12-31", "rera_date": "2028-06-30", "status": "under_construction"},
    "loan_partners": ["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank"],
    "location": {
      "address": "Near Maan Road, Hinjewadi Phase 2, Pune 411057",
      "map_url": "https://maps.google.com/?q=18.5886,73.7011",
      "lat": 18.5886,
      "lng": 73.7011,
      "landmarks": [
        {"name": "Rajiv Gandhi Infotech Park Phase 2", "distance_km": 1.5},
        {"name": "Hinjewadi Metro Line 3 station (under construction)", "distance_km": 2.0},
        {"name": "Mumbai-Bangalore Highway (Wakad)", "distance_km": 9.0},
        {"name": "Ruby Hall Clinic, Hinjewadi", "distance_km": 3.5}
      ]
    },
    "media": {
      "brochure_url": "https://example.com/demo/sahyadri-greens/brochure.pdf",
      "floor_plan_urls": [
        "https://example.com/demo/sahyadri-greens/1bhk.pdf",
        "https://example.com/demo/sahyadri-greens/2bhk.pdf",
        "https://example.com/demo/sahyadri-greens/3bhk.pdf"
      ],
      "emi_calculator_url": "https://example.com/demo/emi?project=sahyadri-greens"
    },
    "site_office_hours": "10:00-19:00, all days",
    "faq": [
      {
        "id": "price",
        "q": {"en": "What is the price?", "hi": "कीमत क्या है?", "mr": "किंमत किती आहे?"},
        "a": {
          "en": "1 BHK starts at 58 lakh, 2 BHK from 78 lakh to 92 lakh, and 3 BHK from 1.15 crore to 1.3 crore, all-inclusive of GST and parking. Stamp duty and registration are extra.",
          "hi": "1 BHK 58 लाख से शुरू है, 2 BHK 78 से 92 लाख, और 3 BHK 1.15 से 1.3 करोड़ तक है। इसमें GST और पार्किंग शामिल है, स्टाम्प ड्यूटी और रजिस्ट्रेशन अलग से।",
          "mr": "1 BHK 58 लाखांपासून सुरू आहे, 2 BHK 78 ते 92 लाख, आणि 3 BHK 1.15 ते 1.3 कोटी आहे. यात GST आणि पार्किंग समाविष्ट आहे, स्टॅम्प ड्युटी आणि रजिस्ट्रेशन वेगळे."
        }
      },
      {
        "id": "possession",
        "q": {"en": "When is possession?", "hi": "पज़ेशन कब मिलेगा?", "mr": "पझेशन कधी मिळेल?"},
        "a": {
          "en": "Target possession is December 2027. The RERA-registered possession date is June 2028.",
          "hi": "टारगेट पज़ेशन दिसंबर 2027 है। RERA में रजिस्टर्ड पज़ेशन डेट जून 2028 है।",
          "mr": "टार्गेट पझेशन डिसेंबर 2027 आहे. RERA मध्ये नोंदवलेली पझेशन तारीख जून 2028 आहे."
        }
      },
      {
        "id": "rera",
        "q": {"en": "Is the project RERA registered?", "hi": "क्या प्रोजेक्ट RERA रजिस्टर्ड है?", "mr": "प्रोजेक्ट RERA नोंदणीकृत आहे का?"},
        "a": {
          "en": "Yes, it is MahaRERA registered, number P52100099901.",
          "hi": "जी हाँ, यह MahaRERA रजिस्टर्ड है, नंबर P52100099901।",
          "mr": "हो, हा MahaRERA नोंदणीकृत आहे, नंबर P52100099901."
        }
      },
      {
        "id": "loan",
        "q": {"en": "Which banks give loans?", "hi": "कौन से बैंक लोन देते हैं?", "mr": "कोणत्या बँका लोन देतात?"},
        "a": {
          "en": "The project is approved with SBI, HDFC Bank, ICICI Bank and Axis Bank. Our team can help with the loan process.",
          "hi": "प्रोजेक्ट SBI, HDFC बैंक, ICICI बैंक और Axis बैंक से अप्रूव्ड है। हमारी टीम लोन प्रोसेस में मदद कर सकती है।",
          "mr": "प्रोजेक्ट SBI, HDFC बँक, ICICI बँक आणि Axis बँकेकडून मंजूर आहे. आमची टीम लोन प्रक्रियेत मदत करू शकते."
        }
      },
      {
        "id": "location",
        "q": {"en": "Where exactly is it?", "hi": "प्रोजेक्ट कहाँ है?", "mr": "प्रोजेक्ट नक्की कुठे आहे?"},
        "a": {
          "en": "Near Maan Road in Hinjewadi Phase 2, about 1.5 km from Infotech Park Phase 2 and 2 km from the upcoming metro station.",
          "hi": "हिंजवडी फेज़ 2 में माण रोड के पास, इन्फोटेक पार्क फेज़ 2 से करीब 1.5 किलोमीटर और आने वाले मेट्रो स्टेशन से 2 किलोमीटर।",
          "mr": "हिंजवडी फेज 2 मध्ये माण रोडजवळ, इन्फोटेक पार्क फेज 2 पासून सुमारे 1.5 किलोमीटर आणि येणाऱ्या मेट्रो स्टेशनपासून 2 किलोमीटर."
        }
      },
      {
        "id": "amenities",
        "q": {"en": "What amenities are there?", "hi": "क्या सुविधाएँ हैं?", "mr": "कोणत्या सुविधा आहेत?"},
        "a": {
          "en": "Clubhouse with gym, swimming pool, kids play area, jogging track, co-working lounge, EV charging and 24x7 security.",
          "hi": "जिम के साथ क्लबहाउस, स्विमिंग पूल, बच्चों का प्ले एरिया, जॉगिंग ट्रैक, को-वर्किंग लाउंज, EV चार्जिंग और 24 घंटे सिक्योरिटी।",
          "mr": "जिमसह क्लबहाऊस, स्विमिंग पूल, मुलांसाठी प्ले एरिया, जॉगिंग ट्रॅक, को-वर्किंग लाउंज, EV चार्जिंग आणि 24 तास सुरक्षा."
        }
      }
    ],
    "objections": [
      {
        "key": "price_too_high",
        "triggers": ["too expensive", "budget nahi", "mehenga", "mahag", "costly", "discount"],
        "response": {
          "en": "I understand. Prices here include GST and parking, and payment is construction-linked, so you pay in stages as the building progresses. Would you like our sales team to share an exact cost sheet for your budget?",
          "hi": "मैं समझता हूँ। यहाँ कीमत में GST और पार्किंग शामिल है, और पेमेंट कंस्ट्रक्शन-लिंक्ड है, यानी काम के साथ किस्तों में देना होता है। क्या हमारी सेल्स टीम आपके बजट के हिसाब से कॉस्ट शीट भेजे?",
          "mr": "मी समजू शकतो. इथे किंमतीत GST आणि पार्किंग समाविष्ट आहे, आणि पेमेंट कन्स्ट्रक्शन-लिंक्ड आहे, म्हणजे बांधकामासोबत टप्प्याटप्प्याने भरायचे. आमची सेल्स टीम तुमच्या बजेटनुसार कॉस्ट शीट पाठवू का?"
        },
        "never_offer": ["discounts", "free gifts", "price negotiation"],
        "next_step": "schedule_callback"
      },
      {
        "key": "location_far",
        "triggers": ["too far", "door hai", "lamb aahe", "traffic", "commute"],
        "response": {
          "en": "Hinjewadi Phase 2 is about 1.5 km from Infotech Park, so for people working there the commute is short, and the metro station is about 2 km away. A site visit is the best way to judge the connectivity yourself.",
          "hi": "हिंजवडी फेज़ 2 इन्फोटेक पार्क से करीब 1.5 किलोमीटर है, तो वहाँ काम करने वालों के लिए आना-जाना आसान है, और मेट्रो स्टेशन लगभग 2 किलोमीटर पर है। कनेक्टिविटी खुद देखने के लिए साइट विज़िट सबसे अच्छा रहेगा।",
          "mr": "हिंजवडी फेज 2 इन्फोटेक पार्कपासून सुमारे 1.5 किलोमीटर आहे, त्यामुळे तिथे काम करणाऱ्यांसाठी प्रवास कमी आहे, आणि मेट्रो स्टेशन सुमारे 2 किलोमीटरवर आहे. कनेक्टिव्हिटी स्वतः पाहण्यासाठी साइट व्हिजिट सर्वात चांगली."
        },
        "next_step": "book_site_visit"
      },
      {
        "key": "possession_delay",
        "triggers": ["delay", "late possession", "ready possession", "kab milega", "ushir"],
        "response": {
          "en": "The target possession is December 2027 and the RERA-committed date is June 2028. RERA registration P52100099901 makes the builder accountable to that date. You can see the construction progress on a site visit.",
          "hi": "टारगेट पज़ेशन दिसंबर 2027 है और RERA में कमिटेड डेट जून 2028 है। RERA नंबर P52100099901 की वजह से बिल्डर उस तारीख के लिए जवाबदेह है। साइट विज़िट पर आप कंस्ट्रक्शन का काम खुद देख सकते हैं।",
          "mr": "टार्गेट पझेशन डिसेंबर 2027 आहे आणि RERA मध्ये दिलेली तारीख जून 2028 आहे. RERA नंबर P52100099901 मुळे बिल्डर त्या तारखेसाठी जबाबदार आहे. साइट व्हिजिटमध्ये तुम्ही बांधकामाची प्रगती स्वतः पाहू शकता."
        },
        "never_offer": ["earlier possession promises", "delay compensation amounts"],
        "next_step": "book_site_visit"
      },
      {
        "key": "loan_emi",
        "triggers": ["loan", "emi", "down payment", "cibil", "bank"],
        "response": {
          "en": "The project is approved with SBI, HDFC, ICICI and Axis. I can send you our EMI calculator link on WhatsApp, and our loan team can check your eligibility. Exact interest rates are decided by the bank.",
          "hi": "प्रोजेक्ट SBI, HDFC, ICICI और Axis से अप्रूव्ड है। मैं आपको WhatsApp पर EMI कैलकुलेटर का लिंक भेज सकता हूँ, और हमारी लोन टीम आपकी एलिजिबिलिटी चेक कर सकती है। ब्याज दर बैंक तय करता है।",
          "mr": "प्रोजेक्ट SBI, HDFC, ICICI आणि Axis कडून मंजूर आहे. मी तुम्हाला WhatsApp वर EMI कॅल्क्युलेटरची लिंक पाठवू शकतो, आणि आमची लोन टीम तुमची पात्रता तपासू शकते. व्याजदर बँक ठरवते."
        },
        "never_offer": ["specific interest rates", "guaranteed loan approval"],
        "next_step": "send_whatsapp_kit"
      },
      {
        "key": "already_bought",
        "triggers": ["already bought", "le liya", "ghetla", "already have a flat", "booked elsewhere"],
        "response": {
          "en": "Congratulations on your new home! If you ever consider a second property for investment, or someone in your family is looking, we would be happy to help. Thank you for your time.",
          "hi": "नए घर के लिए बधाई! अगर कभी इन्वेस्टमेंट के लिए दूसरी प्रॉपर्टी देखें, या परिवार में कोई घर ढूँढ रहा हो, तो हमें मदद करके खुशी होगी। आपके समय के लिए धन्यवाद।",
          "mr": "नवीन घरासाठी अभिनंदन! कधी गुंतवणुकीसाठी दुसरी प्रॉपर्टी पाहायची असेल, किंवा कुटुंबात कोणी घर शोधत असेल, तर आम्हाला मदत करायला आनंद होईल. तुमच्या वेळेबद्दल धन्यवाद."
        },
        "next_step": "mark_not_interested"
      },
      {
        "key": "just_browsing",
        "triggers": ["just checking", "bas dekh raha", "fakt baghtoy", "not now", "exploring"],
        "response": {
          "en": "No problem at all, it is good to explore. Can I send you the brochure and floor plans on WhatsApp so you can compare at your own pace?",
          "hi": "कोई बात नहीं, देखना-समझना अच्छा है। क्या मैं WhatsApp पर ब्रोशर और फ्लोर प्लान भेज दूँ, ताकि आप आराम से तुलना कर सकें?",
          "mr": "काहीच हरकत नाही, पाहणे चांगलेच आहे. मी WhatsApp वर ब्रोशर आणि फ्लोअर प्लॅन पाठवू का, म्हणजे तुम्ही निवांत तुलना करू शकाल?"
        },
        "next_step": "send_whatsapp_kit"
      },
      {
        "key": "call_later",
        "triggers": ["call later", "busy", "baad mein", "nantar", "meeting"],
        "response": {
          "en": "Of course. What time would be convenient for you? I will schedule a call back then.",
          "hi": "बिल्कुल। आपको किस समय बात करना ठीक रहेगा? मैं उस समय कॉल बैक शेड्यूल कर देता हूँ।",
          "mr": "नक्कीच. तुम्हाला कोणत्या वेळी बोलणे सोयीचे होईल? मी त्या वेळी कॉल बॅक ठरवतो."
        },
        "next_step": "schedule_callback"
      }
    ],
    "allowed_claims": [
      "MahaRERA registered: P52100099901",
      "Target possession December 2027; RERA possession date June 2028",
      "Approved by SBI, HDFC Bank, ICICI Bank, Axis Bank",
      "Prices include GST and parking; stamp duty and registration extra",
      "About 1.5 km from Rajiv Gandhi Infotech Park Phase 2"
    ]
  }$json$::jsonb
) on conflict (id) do nothing;

-- ------------------------------------------------ Project 2: Kharadi ------
insert into public.projects (id, org_id, builder_name, name, location, rera_no, config) values (
  'aaaaaaaa-0000-4000-8000-000000000002',
  '11111111-1111-4111-8111-111111111111',
  'Sahyadri Realty',
  'Riverview Residences',
  'Kharadi, Pune',
  'P52100099902',
  $json${
    "company_display_name": {"en": "Sahyadri Realty", "hi": "सह्याद्री रियल्टी", "mr": "सह्याद्री रिअल्टी"},
    "project_display_name": {"en": "Riverview Residences", "hi": "रिवरव्यू रेज़िडेंसेज़", "mr": "रिव्हरव्ह्यू रेसिडेन्सेस"},
    "tagline": "Premium river-facing homes near EON IT Park",
    "bhk_types": [
      {"type": "2BHK", "carpet_sqft": [760, 840],   "price_inr": [11000000, 13000000]},
      {"type": "3BHK", "carpet_sqft": [1150, 1280], "price_inr": [16000000, 19000000]}
    ],
    "price_note": "Prices are all-inclusive of GST and two covered parkings for 3 BHK; stamp duty and registration are extra.",
    "payment_plans": ["Construction-linked plan (CLP)"],
    "towers": 3,
    "floors": "2B+G+28",
    "total_units": 420,
    "land_acres": 4.2,
    "amenities": [
      "Riverside promenade", "Rooftop infinity pool", "Clubhouse with gym and spa",
      "Squash court", "Senior citizens garden", "Banquet hall", "EV charging in every parking",
      "Three-tier security", "Piped gas", "DG power backup for common areas"
    ],
    "possession": {"target_date": "2028-06-30", "rera_date": "2028-12-31", "status": "under_construction"},
    "loan_partners": ["SBI", "HDFC Bank", "Kotak Mahindra Bank", "Bank of Baroda"],
    "location": {
      "address": "Kharadi-Mundhwa Road, Kharadi, Pune 411014",
      "map_url": "https://maps.google.com/?q=18.5515,73.9348",
      "lat": 18.5515,
      "lng": 73.9348,
      "landmarks": [
        {"name": "EON IT Park", "distance_km": 2.0},
        {"name": "World Trade Center Pune", "distance_km": 2.5},
        {"name": "Pune Airport (Lohegaon)", "distance_km": 9.0},
        {"name": "Columbia Asia Hospital, Kharadi", "distance_km": 3.0}
      ]
    },
    "media": {
      "brochure_url": "https://example.com/demo/riverview/brochure.pdf",
      "floor_plan_urls": [
        "https://example.com/demo/riverview/2bhk.pdf",
        "https://example.com/demo/riverview/3bhk.pdf"
      ],
      "emi_calculator_url": "https://example.com/demo/emi?project=riverview"
    },
    "site_office_hours": "10:00-19:00, closed Tuesdays",
    "faq": [
      {
        "id": "price",
        "q": {"en": "What is the price?", "hi": "कीमत क्या है?", "mr": "किंमत किती आहे?"},
        "a": {
          "en": "2 BHK is from 1.1 crore to 1.3 crore and 3 BHK from 1.6 crore to 1.9 crore, all-inclusive of GST. Stamp duty and registration are extra.",
          "hi": "2 BHK 1.1 से 1.3 करोड़ और 3 BHK 1.6 से 1.9 करोड़ तक है, GST शामिल है। स्टाम्प ड्यूटी और रजिस्ट्रेशन अलग से।",
          "mr": "2 BHK 1.1 ते 1.3 कोटी आणि 3 BHK 1.6 ते 1.9 कोटी आहे, GST समाविष्ट आहे. स्टॅम्प ड्युटी आणि रजिस्ट्रेशन वेगळे."
        }
      },
      {
        "id": "possession",
        "q": {"en": "When is possession?", "hi": "पज़ेशन कब मिलेगा?", "mr": "पझेशन कधी मिळेल?"},
        "a": {
          "en": "Target possession is June 2028. The RERA-registered possession date is December 2028.",
          "hi": "टारगेट पज़ेशन जून 2028 है। RERA में रजिस्टर्ड पज़ेशन डेट दिसंबर 2028 है।",
          "mr": "टार्गेट पझेशन जून 2028 आहे. RERA मध्ये नोंदवलेली पझेशन तारीख डिसेंबर 2028 आहे."
        }
      },
      {
        "id": "rera",
        "q": {"en": "Is the project RERA registered?", "hi": "क्या प्रोजेक्ट RERA रजिस्टर्ड है?", "mr": "प्रोजेक्ट RERA नोंदणीकृत आहे का?"},
        "a": {
          "en": "Yes, it is MahaRERA registered, number P52100099902.",
          "hi": "जी हाँ, यह MahaRERA रजिस्टर्ड है, नंबर P52100099902।",
          "mr": "हो, हा MahaRERA नोंदणीकृत आहे, नंबर P52100099902."
        }
      },
      {
        "id": "loan",
        "q": {"en": "Which banks give loans?", "hi": "कौन से बैंक लोन देते हैं?", "mr": "कोणत्या बँका लोन देतात?"},
        "a": {
          "en": "The project is approved with SBI, HDFC Bank, Kotak Mahindra Bank and Bank of Baroda.",
          "hi": "प्रोजेक्ट SBI, HDFC बैंक, कोटक महिंद्रा बैंक और बैंक ऑफ़ बड़ौदा से अप्रूव्ड है।",
          "mr": "प्रोजेक्ट SBI, HDFC बँक, कोटक महिंद्रा बँक आणि बँक ऑफ बडोदाकडून मंजूर आहे."
        }
      },
      {
        "id": "location",
        "q": {"en": "Where exactly is it?", "hi": "प्रोजेक्ट कहाँ है?", "mr": "प्रोजेक्ट नक्की कुठे आहे?"},
        "a": {
          "en": "On Kharadi-Mundhwa Road, about 2 km from EON IT Park and 9 km from Pune airport.",
          "hi": "खराडी-मुंढवा रोड पर, EON IT पार्क से करीब 2 किलोमीटर और पुणे एयरपोर्ट से 9 किलोमीटर।",
          "mr": "खराडी-मुंढवा रोडवर, EON IT पार्कपासून सुमारे 2 किलोमीटर आणि पुणे विमानतळापासून 9 किलोमीटर."
        }
      },
      {
        "id": "amenities",
        "q": {"en": "What amenities are there?", "hi": "क्या सुविधाएँ हैं?", "mr": "कोणत्या सुविधा आहेत?"},
        "a": {
          "en": "Riverside promenade, rooftop infinity pool, clubhouse with gym and spa, squash court, senior citizens garden and EV charging in every parking.",
          "hi": "रिवरसाइड प्रोमेनेड, रूफटॉप इन्फिनिटी पूल, जिम और स्पा वाला क्लबहाउस, स्क्वैश कोर्ट, सीनियर सिटिज़न गार्डन और हर पार्किंग में EV चार्जिंग।",
          "mr": "रिव्हरसाइड प्रोमेनेड, रूफटॉप इन्फिनिटी पूल, जिम आणि स्पा असलेले क्लबहाऊस, स्क्वॅश कोर्ट, ज्येष्ठ नागरिक उद्यान आणि प्रत्येक पार्किंगमध्ये EV चार्जिंग."
        }
      }
    ],
    "objections": [
      {
        "key": "price_too_high",
        "triggers": ["too expensive", "budget nahi", "mehenga", "mahag", "costly", "discount"],
        "response": {
          "en": "I understand, it is a premium project. The price includes GST, and payment is construction-linked, so it is spread over the build period. Shall I ask our sales team to share a detailed cost sheet?",
          "hi": "मैं समझता हूँ, यह प्रीमियम प्रोजेक्ट है। कीमत में GST शामिल है, और पेमेंट कंस्ट्रक्शन-लिंक्ड है, तो रकम बनने के समय में बँट जाती है। क्या सेल्स टीम से डिटेल्ड कॉस्ट शीट भिजवाऊँ?",
          "mr": "मी समजू शकतो, हा प्रीमियम प्रोजेक्ट आहे. किंमतीत GST समाविष्ट आहे, आणि पेमेंट कन्स्ट्रक्शन-लिंक्ड आहे, त्यामुळे रक्कम बांधकामाच्या काळात विभागली जाते. सेल्स टीमकडून सविस्तर कॉस्ट शीट पाठवू का?"
        },
        "never_offer": ["discounts", "free gifts", "price negotiation"],
        "next_step": "schedule_callback"
      },
      {
        "key": "location_far",
        "triggers": ["too far", "door hai", "lamb aahe", "traffic", "commute"],
        "response": {
          "en": "Kharadi is about 2 km from EON IT Park and World Trade Center, and around 9 km from the airport. Visiting the site is the best way to see the connectivity.",
          "hi": "खराडी EON IT पार्क और वर्ल्ड ट्रेड सेंटर से करीब 2 किलोमीटर, और एयरपोर्ट से लगभग 9 किलोमीटर है। कनेक्टिविटी देखने के लिए साइट विज़िट सबसे अच्छा है।",
          "mr": "खराडी EON IT पार्क आणि वर्ल्ड ट्रेड सेंटरपासून सुमारे 2 किलोमीटर, आणि विमानतळापासून सुमारे 9 किलोमीटर आहे. कनेक्टिव्हिटी पाहण्यासाठी साइट व्हिजिट सर्वात चांगली."
        },
        "next_step": "book_site_visit"
      },
      {
        "key": "possession_delay",
        "triggers": ["delay", "late possession", "ready possession", "kab milega", "ushir"],
        "response": {
          "en": "The target possession is June 2028 and the RERA-committed date is December 2028, under MahaRERA number P52100099902. You can check construction progress on a site visit.",
          "hi": "टारगेट पज़ेशन जून 2028 है और RERA कमिटेड डेट दिसंबर 2028 है, MahaRERA नंबर P52100099902 के तहत। साइट विज़िट पर आप काम की प्रगति देख सकते हैं।",
          "mr": "टार्गेट पझेशन जून 2028 आहे आणि RERA मध्ये दिलेली तारीख डिसेंबर 2028 आहे, MahaRERA नंबर P52100099902 अंतर्गत. साइट व्हिजिटमध्ये तुम्ही कामाची प्रगती पाहू शकता."
        },
        "never_offer": ["earlier possession promises", "delay compensation amounts"],
        "next_step": "book_site_visit"
      },
      {
        "key": "loan_emi",
        "triggers": ["loan", "emi", "down payment", "cibil", "bank"],
        "response": {
          "en": "The project is approved with SBI, HDFC, Kotak and Bank of Baroda. I can WhatsApp you the EMI calculator, and our loan team can check eligibility. The bank decides the exact interest rate.",
          "hi": "प्रोजेक्ट SBI, HDFC, कोटक और बैंक ऑफ़ बड़ौदा से अप्रूव्ड है। मैं WhatsApp पर EMI कैलकुलेटर भेज सकता हूँ, और लोन टीम एलिजिबिलिटी चेक कर सकती है। ब्याज दर बैंक तय करता है।",
          "mr": "प्रोजेक्ट SBI, HDFC, कोटक आणि बँक ऑफ बडोदाकडून मंजूर आहे. मी WhatsApp वर EMI कॅल्क्युलेटर पाठवू शकतो, आणि लोन टीम पात्रता तपासू शकते. व्याजदर बँक ठरवते."
        },
        "never_offer": ["specific interest rates", "guaranteed loan approval"],
        "next_step": "send_whatsapp_kit"
      },
      {
        "key": "already_bought",
        "triggers": ["already bought", "le liya", "ghetla", "already have a flat", "booked elsewhere"],
        "response": {
          "en": "Congratulations on your new home! If you or your family ever look at another property, we would be glad to help. Thank you for your time.",
          "hi": "नए घर के लिए बधाई! अगर आप या आपका परिवार कभी दूसरी प्रॉपर्टी देखें, तो हमें मदद करके खुशी होगी। आपके समय के लिए धन्यवाद।",
          "mr": "नवीन घरासाठी अभिनंदन! तुम्ही किंवा तुमचे कुटुंब कधी दुसरी प्रॉपर्टी पाहणार असाल, तर आम्हाला मदत करायला आनंद होईल. तुमच्या वेळेबद्दल धन्यवाद."
        },
        "next_step": "mark_not_interested"
      },
      {
        "key": "just_browsing",
        "triggers": ["just checking", "bas dekh raha", "fakt baghtoy", "not now", "exploring"],
        "response": {
          "en": "That is perfectly fine. Shall I send the brochure and floor plans on WhatsApp so you can have a look whenever convenient?",
          "hi": "बिल्कुल ठीक है। क्या मैं WhatsApp पर ब्रोशर और फ्लोर प्लान भेज दूँ, ताकि आप सुविधा से देख सकें?",
          "mr": "अगदी ठीक आहे. मी WhatsApp वर ब्रोशर आणि फ्लोअर प्लॅन पाठवू का, म्हणजे तुम्ही सोयीने पाहू शकाल?"
        },
        "next_step": "send_whatsapp_kit"
      },
      {
        "key": "call_later",
        "triggers": ["call later", "busy", "baad mein", "nantar", "meeting"],
        "response": {
          "en": "Sure. What time works best for you? I will schedule a call back.",
          "hi": "ज़रूर। आपके लिए कौन सा समय ठीक रहेगा? मैं कॉल बैक शेड्यूल कर देता हूँ।",
          "mr": "नक्की. तुमच्यासाठी कोणती वेळ योग्य राहील? मी कॉल बॅक ठरवतो."
        },
        "next_step": "schedule_callback"
      }
    ],
    "allowed_claims": [
      "MahaRERA registered: P52100099902",
      "Target possession June 2028; RERA possession date December 2028",
      "Approved by SBI, HDFC Bank, Kotak Mahindra Bank, Bank of Baroda",
      "Prices include GST; stamp duty and registration extra",
      "About 2 km from EON IT Park"
    ]
  }$json$::jsonb
) on conflict (id) do nothing;

-- ------------------------------------ channel partner access (broker) ------
insert into public.project_access (project_id, org_id) values
  ('aaaaaaaa-0000-4000-8000-000000000001', '22222222-2222-4222-8222-222222222222'),
  ('aaaaaaaa-0000-4000-8000-000000000002', '22222222-2222-4222-8222-222222222222')
on conflict do nothing;

-- ------------------------------------------------------------ visit slots ---
-- Sahyadri Greens: weekdays 11-13 & 15-18 (cap 4), weekends 10-13 & 14-18 (cap 8)
insert into public.visit_slots (project_id, day_of_week, start_time, end_time, capacity)
select 'aaaaaaaa-0000-4000-8000-000000000001', d, s.start_time, s.end_time,
       case when d >= 6 then 8 else 4 end
from generate_series(1, 7) as d
cross join lateral (
  values
    (case when d >= 6 then time '10:00' else time '11:00' end, time '13:00'),
    (case when d >= 6 then time '14:00' else time '15:00' end, time '18:00')
) as s(start_time, end_time)
on conflict (project_id, day_of_week, start_time) do nothing;

-- Riverview Residences: closed Tuesday (2); 11-14 & 16-19, cap 3 weekdays / 6 weekends
insert into public.visit_slots (project_id, day_of_week, start_time, end_time, capacity)
select 'aaaaaaaa-0000-4000-8000-000000000002', d, s.start_time, s.end_time,
       case when d >= 6 then 6 else 3 end
from generate_series(1, 7) as d
cross join (values (time '11:00', time '14:00'), (time '16:00', time '19:00')) as s(start_time, end_time)
where d <> 2
on conflict (project_id, day_of_week, start_time) do nothing;

-- -------------------------------------------------------- demo campaigns ---
-- Left in 'draft' so nothing dials until a human activates them.
insert into public.campaigns (id, org_id, project_id, name, status, calling_window, max_concurrency) values
  ('cccccccc-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111',
   'aaaaaaaa-0000-4000-8000-000000000001', 'Sahyadri Greens - Meta leads (Demo)', 'draft',
   '{"start":"10:00","end":"20:00","days":[1,2,3,4,5,6,7]}', 2),
  ('cccccccc-0000-4000-8000-000000000002', '22222222-2222-4222-8222-222222222222',
   'aaaaaaaa-0000-4000-8000-000000000002', 'Riverview - Broker outreach (Demo)', 'draft',
   '{"start":"10:00","end":"19:00","days":[1,3,4,5,6,7]}', 1)
on conflict (id) do nothing;
