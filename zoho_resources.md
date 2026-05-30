# Catalyst by Zoho — Supported Features & Services

Reference for the KSP Crime Intelligence Platform submission.

> **Deployment via Catalyst is mandatory for all submissions, without exception.**
>
> Use the listed Catalyst service for any matching capability in the solution. Using a third-party alternative when a Catalyst service is available may affect the validity of the submission.

## Service mapping

| #   | Capability                                                                          | Required Catalyst Service                              |
| --- | ----------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 1   | Serverless functions / backend logic                                                | Catalyst Serverless (Functions)                        |
| 2   | Docker image deployment                                                             | Catalyst AppSail (custom OCI runtime)                  |
| 3   | Full web app in a managed runtime                                                   | Catalyst AppSail (managed runtime)                     |
| 4   | Frontend / SPA / Next.js / static site                                              | Catalyst Slate or Web Client Hosting                   |
| 5   | Custom domain + SSL                                                                 | Catalyst Domain Mappings                               |
| 6   | Relational database                                                                 | Catalyst Data Store                                    |
| 7   | Unstructured / semi-structured data                                                 | Catalyst NoSQL                                         |
| 8   | Object / blob storage (S3-style)                                                    | Catalyst Stratus                                       |
| 9   | Cache                                                                               | Catalyst Cache                                         |
| 10  | Full-text search (within Data Store)                                                | Catalyst Data Store                                    |
| 11  | Text LLMs / RAG / knowledge bases                                                   | Catalyst QuickML (LLM Serving, RAG)                    |
| 12  | No-code ML pipelines                                                                | Catalyst QuickML                                       |
| 13  | Automated model training (tabular)                                                  | Catalyst Zia AutoML                                    |
| 14  | OCR / Face / Text Analytics / Image Mod / Object Recognition / Barcode / ID Scanner | Catalyst Zia Services                                  |
| 15  | Voice services / models (speech-to-text, text-to-speech, translation)               | Catalyst Zia Services                                  |
| 16  | PDF / image-based report generation, screenshots, headless browser, scraping        | Catalyst SmartBrowz                                    |
| 17  | User auth / login / signup                                                          | Catalyst Authentication                                |
| 18  | API routing, throttling, and auth in front of Functions or Web Client Hosting       | Catalyst API Gateway                                   |
| 19  | OAuth tokens for Zoho / 3rd-party services                                          | Catalyst Connections                                   |
| 20  | Scheduled jobs / cron / job pools                                                   | Catalyst Cron (Cloud Scale) or Catalyst Job Scheduling |
| 21  | Reacting to in-project events (DB inserts, file uploads, signups, etc.)             | Catalyst Signals + Event Functions                     |
| 22  | Cross-app event bus / event routing                                                 | Catalyst Signals                                       |
| 23  | Multi-step workflow / orchestration with branches and parallel steps                | Catalyst Circuits                                      |
| 24  | Transactional email                                                                 | Catalyst Mail                                          |
| 25  | Push notifications (web / Android / iOS)                                            | Catalyst Push Notifications                            |
| 26  | CI/CD                                                                               | Catalyst Pipelines                                     |
