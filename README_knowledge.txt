BETNAVA MEDICAL CENTER KNOWLEDGE BASE
======================================

File: knowledge.jsonl
Created: 2026-01-17
Source: https://www.mc-betnava.si

OVERVIEW
--------
This knowledge base contains medical information scraped from the BETNAVA Medical Center website.
It includes information about services, medical conditions, treatments, pricing, doctors, and appointment booking.

FILE STATISTICS
--------------
Total entries: 61
Total characters: 160,763
Average entry size: 2,635 characters
Format: JSONL (JSON Lines - one JSON object per line)

CONTENT CATEGORIES
------------------
- Dermatology Services: 9 entries
- Orthopedics Services: 1 entry
- Ophthalmology Services: 2 entries
- Cosmetics Services: 1 entry
- Pricing Information: 4 entries
- Doctor Profiles: 5 entries
- Medical Conditions: 8 entries
- Treatments/Procedures: 14 entries
- Appointment/Booking: 1 entry
- Advice/Tips: 16 entries

JSONL FORMAT
-----------
Each line is a JSON object with the following structure:
{
  "text": "Main content of the page...",
  "metadata": {
    "source": "https://www.mc-betnava.si/...",
    "title": "Page title"
  }
}

CONTENT PROCESSING
-----------------
1. All URLs were scraped using standard Python libraries (urllib)
2. Navigation menus and footer content were removed
3. All instances of "MC Betnava" and "Zdravstveni center Betnava" were replaced with "BETNAVA"
4. Content focuses on:
   - Medical information about conditions and diseases
   - Treatment procedures and options
   - Service descriptions and availability
   - Pricing information
   - Doctor credentials and specializations
   - Appointment and booking information

MEDICAL SPECIALTIES COVERED
---------------------------
1. Dermatology (Dermatologija)
   - Skin conditions (acne, rosacea, psoriasis, etc.)
   - Sexually transmitted infections
   - Laser treatments
   - Aesthetic procedures (Botox, fillers, etc.)
   - Skin examinations and dermatoscopy

2. Orthopedics (Ortopedija)
   - Joint conditions (osteoarthritis, etc.)
   - Surgical and conservative treatments
   - Arthroscopy
   - Artificial joint replacements

3. Ophthalmology (Oftalmologija)
   - Eye examinations
   - Eye care services

4. Cosmetics (Kozmetika)
   - Facial care
   - Aesthetic treatments

PRICING INFORMATION
------------------
The knowledge base includes pricing for:
- Dermatological examinations and procedures
- Orthopedic consultations
- Ophthalmological services
- Cosmetic treatments

All prices are listed in EUR.

USAGE NOTES
-----------
- This knowledge base is designed for chatbot/AI assistant use
- Content is in Slovenian language
- All URLs are preserved in metadata for reference
- Content has been cleaned but maintains medical accuracy
- Suitable for RAG (Retrieval-Augmented Generation) systems

SCRIPTS USED
-----------
- scrape_betnava_v2.py: Main scraping script
- clean_knowledge_v2.py: Content cleaning script

CONTACT INFORMATION (from website)
---------------------------------
Location: Ljubljanska ulica 89, Maribor
Dermatology: 02 292 77 20
Orthopedics: 02 292 77 20
Ophthalmology: 02 292 77 20
