# **Agentic Lead Generation Specification for PaperPlane**

## **1\. System Context: PaperPlane OmniChannel**

**PaperPlane** is an event-driven, Omni-channel messaging system designed for "Student Recruitment" and "Medical Tourism" agencies. It serves as the central communication hub, decoupling message ingestion from processing to ensure scalability.

* **Core Architecture:**  
  * **Backend:** FastAPI (Python 3.9+)  
  * **Event Bus:** Confluent Kafka  
  * **Messaging:** Twilio (WhatsApp only for now)  
  * **Infrastructure:** Google Cloud  
* **Existing Workflow:**  
  * Inbound messages (WhatsApp) → Webhook → Kafka (whatsapp\_inbound) → Consumer.  
  * Outbound messages → API → Kafka (whatsapp\_outbound) → Twilio.  
* **Key Features:**  
  * AI Agents for Lead Gen & Support.  
  * Custom Form Builder (QR Code ingestion).  
  * Consultation Booking.

### **B2B2C (Business-to-Business-to-Consumer)** User Story.

#### **🎭 The Actors**
1.  **Allen:** The Agency Owner (User of PaperPlane).
2.  **The Partner (B2):** A local entity (e.g., High School Principal, Local Clinic Doctor) found by the AI.
3.  **The Prospect (C):** The actual student or patient.

#### **Phase 1: Partner Acquisition (B2B)**
1.  **Initiation:** Allen logs into PaperPlane and activates the **AI Lead Gen Agent**. He inputs: `City: Nairobi`, `Market: Student Recruitment`, `Strategy: High School Counselors`.
2.  **Discovery:** The AI Agent (acting as the Scout) scans public maps and directories. It identifies "St. Mary’s International School" and finds the public contact number for the "Head of Guidance Counseling," Mr. Kamau.
3.  **Lead Presentation:** The AI generates a "Partner Lead" entry in Allen's dashboard. Allen reviews Mr. Kamau's profile and clicks **"Approve & Engage"**.
4.  **B2B Outreach:** The AI generates a customized outreach template: *"Hi Mr. Kamau, I see St. Mary's has great A-Level results. I help students secure scholarships in the UK. Open to a chat?"*.
5.  **Conversion:** Allen sends this via the Omni-channel system (WhatsApp). They chat, and Mr. Kamau agrees to refer his students to Allen.

#### **Phase 2: The Handoff (The "Bridge")**
6.  **Tool Creation:** Allen uses PaperPlane’s **Custom Form Builder** to create a specific landing page titled: *"St. Mary's Student Assessment Form"*. He generates a **QR Code** for this form.
7.  **Distribution:** Allen sends the QR code to Mr. Kamau via WhatsApp.
8.  **Ingestion:** Mr. Kamau prints the QR code and puts it on the school notice board, or forwards the link to his graduating class group chat.

#### **Phase 3: Prospect Engagement (B2C)**
9.  **Data Entry:** A student, **Sarah**, scans the QR code and fills in her details (Name, Grade, Dream Country) via the form.
10. **System Activation:**
    * Sarah's data hits the `whatsapp_inbound` Kafka topic.
    * PaperPlane creates a new "Prospect" record linked to "Source: St. Mary's Partner".
11. **AI Engagement:** The AI Agent immediately sends a WhatsApp to Sarah: *"Hi Sarah! Mr. Kamau from St. Mary's let us know you're interested in studying abroad. I have your details. Do you have a specific country in mind?"*
12. **Nurturing:** Sarah replies. The AI Agent answers her Q&A regarding universities, utilizing the system's "Assist with common Q&A" feature. Allen monitors the chat in the background.
13. **Conversion:** When Sarah is ready, the AI prompts her to "Book a Consultation" with Allen.
14. **Closing:** Allen steps in, finalizes the university application, and moves Sarah to the "Client" stage, where the AI switches to sending flight/rental deals.


### **💡 Design decision justification**
* **No Budget for Ads:** We rely on the *Partner's* existing authority to get the lead, rather than paying Facebook/Instagram to find Sarah.
* **No CRM Integration:** We use the **Form Builder/QR Code** as the data entry point, bypassing the need to integrate with the Partner's internal systems.
* **High Trust:** Sarah trusts Allen immediately because the introduction came from her teacher (Mr. Kamau), resulting in much higher conversion rates than cold outreach.


## **2\. Agentic Workflow Overview (B2B2C)**

The **Lead Generation Module** operates on a **B2B2C (Business-to-Business-to-Consumer)** model. Due to "Zero Budget" constraints (no paid ads/API access), the system uses **Open Source Intelligence (OSINT)** to identify **Channel Partners** (B2B) who control access to the target end-users (B2C).

### **The Objective**

Identify, Enrich, and Draft Outreach for "Channel Partners" in a specific target city.

* **Input:** Target City (e.g., "Nairobi"), Market Vertical ("Student Recruitment" or "Medical Tourism").  
* **Output:** A structured Lead object containing Partner details and a hyper-personalized outreach draft, pushed to the lead\_generated Kafka topic.

### **The Pipeline Phases**

1. **Discovery (The Scout):** Identifies potential partners (High Schools, Clinics) using public search.  
2. **Enrichment (The Researcher):** Scrapes partner websites to extract key contacts (Principals, Doctors) and contact info.  
3. **Strategy (The Strategist):** Analyzes gathered data to draft a contextual, "warm" WhatsApp opening message.

## **3\. ADK Architecture Design**

The system utilizes the **Google Agent Development Kit (ADK)**. The architecture follows a **Sequential Pattern**, where the output of one agent becomes the context for the next.

* **Orchestration Pattern:** SequentialAgent  
* **Hosting:** Background Worker Service (Python) triggered by FastAPI.  
* **Models:**  
  * gemini-1.5-flash (Scouting & Research \- High speed/Low cost).  
  * gemini-1.5-pro (Strategy \- High reasoning for persuasive copy).

### **Agent Map**

| Agent Role | Model | Responsibility | Tools |
| :---- | :---- | :---- | :---- |
| **Root Agent** | N/A | Pipeline Orchestrator | LeadGenPipeline |
| **Scout** | Flash | Search & List Generation | Google Search / ddg\_search |
| **Researcher** | Flash | Deep Dive & Extraction | web\_scraper (BS4/Playwright) |
| **Strategist** | Pro | Content Generation | None (Pure LLM) |

## **4\. Detailed Agent Specifications**

### **A. The Scout Agent (Discovery)**

**Goal:** Generate a raw list of potential Channel Partners based on the market vertical.

* **System Instruction:**You are a Digital Scout. Your goal is to find "Channel Partners" in a specific city who hold influence over our target audience.  
  Strategy:  
  1. If Market is **"Student Recruitment"**, search for "Feeder Institutions":  
     * International High Schools (offering IB/IGCSE).  
     * IELTS/TOEFL Coaching Centers.  
     * A-Level Tuition Centers.  
  2. If Market is **"Medical Tourism"**, search for "Referral Nodes":  
     * Diagnostic Centers (MRI/CT Scan labs).  
     * Specialist Clinics (Orthopedic, Cardiac) that lack surgical facilities.  
     * Expat Community Centers.

**Output:** Return a JSON list of { "entity\_name": str, "website\_url": str, "type": str }.

### **B. The Researcher Agent (Enrichment)**

**Goal:** Visit the specific URLs found by the Scout and extract actionable contact data.

* **System Instruction:**You are an Intelligence Researcher. You will be given a URL. Your job is to extract specific contact details to enable direct outreach.  
  Task:  
  1. Visit the website (focus on 'Contact', 'Staff', 'About Us', 'Leadership' pages).  
  2. Extract the **Name** of the decision-maker (Principal, Head Doctor, Director).  
  3. Extract **Direct Contact** info (Email, Phone/WhatsApp).  
  4. Extract **One Key Fact** for personalization (e.g., "Recently won an award," "Opened a new branch," "School Motto").

**Output:** A JSON object { "decision\_maker": str, "contact\_info": str, "key\_fact": str, "verified\_url": str }.

### **C. The Strategist Agent (Qualification & Drafting)**

**Goal:** Create the "Hook" that Allen (the user) will send.

* **System Instruction:**You are a Senior Sales Strategist named "Allen". You are writing a WhatsApp message to a potential partner.  
  Context:  
  * We are a premium agency (Student Recruitment or Medical Tourism).  
  * We want to partner with them so they refer their clients/students to us.

  Task:  
    Draft a SHORT, casual, but professional WhatsApp message (max 2 sentences).

  * Use the **Decision Maker's Name**.  
  * Reference the **Key Fact** found by the Researcher to prove we did our homework.  
  * End with a low-friction question (e.g., "Open to a quick chat?").

**Tone:** Professional, direct, no fluff.

## **5\. Technical Integration (FastAPI & Kafka)**

### **Trigger Flow**

1. **Endpoint:** POST /api/agents/lead-gen  
   * **Payload:** { "city": "Dubai", "market": "Student Recruitment" }  
2. **Process:**  
   * FastAPI enqueues a job or triggers the ADK Runner asynchronously.  
   * ADK SequentialAgent executes: Scout → Researcher → Strategist.  
3. **Completion:**  
   * The Result is formatted into the **Lead Object**.  
   * Producer pushes payload to Kafka topic: lead\_generated.

### **Kafka Payload Schema (lead\_generated)**
```
{  
  "event\_type": "lead\_discovered",  
  "timestamp": "2023-10-27T10:00:00Z",  
  "data": {  
    "source\_agent": "adk\_v1",  
    "market": "Student Recruitment",  
    "city": "Dubai",  
    "partner\_profile": {  
      "name": "Gems Wellington Academy",  
      "url": "\[https://www.gemswellingtonacademy-siliconoasis.com/\](https://www.gemswellingtonacademy-siliconoasis.com/)",  
      "contact\_person": "Mrs. Sarah O'Regan",  
      "contact\_method": "+97145159000"  
    },  
    "ai\_context": {  
      "key\_insight": "Offers IB Diploma and BTEC courses.",  
      "draft\_message": "Hi Mrs. O'Regan, noticed GEMS Wellington's strong BTEC results this year. We specialize in placing BTEC grads into top UK unis—open to a quick chat about a partnership?"  
    }  
  }  
}
```
## **6\. User Experience (The "Allen" Flow)**

1. **Notification:** Allen receives a ping on the PaperPlane dashboard: *"New Potential Partner Found: Gems Wellington Academy"*.  
2. **Review:** Allen views the lead card. He sees the URL, the Principal's name, and the AI-drafted message.  
3. **Action:**  
   * **Edit:** Allen tweaks the message draft.  
   * **Approve:** Allen clicks "Send".  
4. **Execution:** The approved message payload is moved to the whatsapp\_outbound Kafka topic for delivery via Twilio.