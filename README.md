# **PaperPlane OmniChannel ✈️**

An event-driven Omni-channel messaging system built with **FastAPI**, **Confluent Kafka**, and **Twilio**.

This system acts as a central "brain" for handling customer communication. It decouples message ingestion from message processing using Kafka topics, ensuring scalability and reliability.

## **🏗 Architecture**

The system follows an event-driven workflow:

1. **Inbound (User \-\> Business):**  
   * User sends a WhatsApp message.  
   * Twilio Webhook hits FastAPI (/webhook/twilio).  
   * FastAPI produces an event to the whatsapp\_inbound Kafka topic.  
   * A background consumer listens to this topic and processes the message (e.g., logging, triggering AI, etc.).  
2. **Outbound (Business \-\> User):**  
   * Internal service (or API call) requests to send a message via (/api/send-message).  
   * FastAPI produces an event to the whatsapp\_outbound Kafka topic.  
   * A background consumer listens to this topic and calls the Twilio API to deliver the message.

## **🛠 Tech Stack**

* **Language:** Python 3.9+  
* **Framework:** FastAPI  
* **Event Streaming:** Confluent Kafka  
* **Messaging Provider:** Twilio (WhatsApp Sandbox)  
* **Tunneling (Dev):** ngrok

## **🚀 Prerequisites**

Before running the application, ensure you have:

* [Python 3.10+](https://www.python.org/downloads/)  
* [ngrok](https://ngrok.com/download) (for exposing local server to Twilio)  
* A **Confluent Cloud** basic cluster.  
* A **Twilio Account** (Free trial works).

## **⚙️ Configuration**

1. Clone the repository:  
   git clone \[https://github.com/yourusername/paperplane-omnichannel.git\](https://github.com/yourusername/paperplane-omnichannel.git)  
   cd paperplane-omnichannel

2. Create a virtual environment:  
   python \-m venv venv  
   source venv/bin/activate  \# On Windows: venv\\Scripts\\activate

3. Install dependencies:  
   pip install \-r requirements.txt  
   \# Ensure python-multipart is installed for webhook handling  
   pip install python-multipart

4. Create a .env file in the root directory:  
   \# \--- Google Cloud (Optional for now) \---  
   GCP\_PROJECT\_ID=your-gcp-project-id  
   GCP\_REGION=us-central1

   \# \--- Confluent Kafka \---  
   KAFKA\_BOOTSTRAP\_SERVERS=pkc-xxxxx.region.gcp.confluent.cloud:9092  
   KAFKA\_API\_KEY=your\_kafka\_api\_key  
   KAFKA\_API\_SECRET=your\_kafka\_secret

   \# \--- Twilio \---  
   TWILIO\_ACCOUNT\_SID=your\_twilio\_sid  
   TWILIO\_AUTH\_TOKEN=your\_twilio\_auth\_token  
   TWILIO\_NUMBER=whatsapp:+14155238886

## **🏃‍♂️ Running the Application**

### **1\. Start the Server**

Start the FastAPI server with hot-reloading enabled:

uvicorn main:app \--reload

*Server will start at http://127.0.0.1:8000*

### **2\. Expose Localhost (ngrok)**

In a separate terminal, expose your local port 8000 to the internet so Twilio can reach it:

ngrok http 8000

Copy the HTTPS URL generated (e.g., https://abcd-123.ngrok-free.app).

### **3\. Configure Twilio Webhook**

1. Go to **Twilio Console \> Messaging \> Settings \> WhatsApp Sandbox Settings**.  
2. In the **"When a message comes in"** field, paste your ngrok URL with the webhook path:  
   https://\<your-ngrok-url\>/api/ppl/twilio/webhook

3. Set the method to **POST**.  
4. Click **Save**.

## **🧪 Testing**

### **Inbound (Client \-\> Business)**

1. Join your Twilio Sandbox (send the join code, e.g., join paper-plane to the sandbox number).  
2. Send a message like "Hello World" from your WhatsApp to the Sandbox number.  
3. Check your FastAPI terminal. You should see:  
   \[INBOUND EVENT RECEIVED\]: From whatsapp:+1xxxx: Hello World

### **Outbound (Business \-\> Client)**

Use curl or Postman to trigger an outbound message:

curl \-X POST "http://localhost:8000/api/send-message" \\  
     \-H "Content-Type: application/json" \\  
     \-d '{  
           "to\_number": "whatsapp:+1\<YOUR\_NUMBER\>",  
           "message\_body": "Hello from PaperPlane\!"  
         }'

*Note: Since you are on a Twilio Free Trial, you can only send messages to verified numbers (users who have joined your sandbox).*

## Run the serverside application
```
uvicorn app.main:app --reload    
```
## Get a ngrok url for testing
```
ngrok http 8000
```

## **🐞 Troubleshooting**

* AssertionError: The python-multipart library must be installed:  
  Run pip install python-multipart. This is required for FastAPI to parse Twilio's form data.  
* Kafka Timeout / Auth Errors:  
  Double-check your KAFKA\_BOOTSTRAP\_SERVERS, API\_KEY, and SECRET in the .env file. Ensure your network allows connection to Confluent ports (usually 9092).


## Core features:

### Student Recruitment and Medical Tourism Agencies
1. Omni channel - Instant messaging integration.
2. AI agents:
    - Lead Generation
    - Service monitoring (flight prices/rental prices).
    - Assist with common Q&A.
    - Outreach message templates - email and instant messaging.
3. Custom form builder with file upload capability. Sharable form using qr code or urls.
4. Pushing ads to social media.
5. Setting calendar slots for consultation.

### Agency clients
1. Consultation booking.
2. Notifications for latest updates.
3. Upload and update documentation.

## User story
1. The autonomous ai agent generates the list.
2. Allen selects from the list of prospects.
3. AI generates a short outreach message template.
4. Allen uses message template to do outreach over instant messaging using omni channel.
5. Allen and user go back and forth and allen convinces the prospect.
6. Client books a consultation with Allen.
7. Allen generates the form that is specific for his client.
8. Client provides necessary information- name, address, certificates etc.
9. Allen's team can processes the collected data and updates the progress.
10. Client starts asking Allen for updates and other related questions. AI agent assists to answer these questions. Allen also remains in the loop. Allen can choose to disable ai assisted messaging for clients with closed deals.
11. When progress reaches a certain stage ai agent starts providing flight and rental deals. Allen can pass these to the client or configure the ai to send it to the client.
12. Client chooses the flight/rental deals they like. Allen's team does the remaining processing.
13. Allen finally provides all the documentation the client needs to start their journey.
14. Client and Allen stay in touch via omni-channel.



