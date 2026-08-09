# Fake News / Claim Checker

## Overview

This project is a web application that helps users verify whether a piece of news, a claim, or a statement is likely to be true, false, or misleading. A user can submit a claim as typed text, spoken input, an uploaded image (such as a screenshot of a headline or a forwarded message), or a direct link to an image. The system analyzes the claim through a layered pipeline that combines live web search, source-grounded verification against retrieved news articles, and a fallback machine learning classifier for cases where no external verification is possible. The result is returned with a verdict, a confidence score, a plain-language explanation, and, where relevant, the specific sources that were consulted.

The application is built as a Flask backend with a single-page frontend. The frontend supports microphone input for hands-free claim entry and text-to-speech playback of results, in addition to standard text and image submission.

Before reaching the main interface, a first-time visitor is shown a lightweight "I'm not a robot" verification screen (Google reCAPTCHA v2). Once verified, the browser stays verified indefinitely until the user explicitly logs out, so returning visitors go straight to the main app.

## How the Verification Pipeline Works

When a claim is submitted, it goes through the following stages:

1. **Classification and extraction.** The claim is first analyzed to determine whether it describes a specific news event (a political announcement, an incident, a sports result, a government scheme, and so on) or a general fact that is not tied to a particular moment in time (a scientific, historical, or otherwise timeless statement). At the same time, a short, search-friendly version of the claim is extracted. Both of these are done in a single call to keep the pipeline fast.

2. **General facts.** If the claim is a general fact, it is checked using two independent sources: a live web search performed through Groq, and Google Gemini's own trained knowledge. Both are consulted in parallel and their verdicts are combined into a single result.

3. **News events, first pass.** If the claim concerns a specific news event, the same live search and independent-knowledge check is tried first, since it can resolve most claims directly without needing a separate article search. If this step produces a confident verdict of Real or Fake, that result is returned immediately.

4. **News events, second pass.** If the first pass is not confident enough, the system falls back to a targeted search of recent news articles through NewsData.io. If related articles are found, both Groq and Gemini are asked to compare the original claim against this retrieved context and produce a verdict grounded specifically in those articles, rather than in general knowledge. This reduces the risk of the models guessing or hallucinating an answer.

5. **Final fallback.** If no related articles can be found at all, the system falls back to a locally trained Logistic Regression classifier. This model was trained on a labeled dataset of real and fake news articles and makes its prediction based on writing style, tone, and vocabulary rather than by checking any external source. Because this fallback is not grounded in retrieved evidence, results from this stage are presented as a lower-confidence signal, along with the specific words that most influenced the model's decision.

Throughout the pipeline, whenever two independent engines are consulted and they disagree, the result is marked as uncertain rather than silently picking one side. Technical failures on one engine, such as a missing API key or a rate limit, do not drag down a confident result from the other engine.

## Image-Based Claim Checking

In addition to text, the application accepts an uploaded image file or a direct URL to an image. In both cases, Google Gemini's vision capability is used to read the visible text from the image, whether it is a screenshot, a social media post, or a forwarded message. The extracted text is then passed through the same verification pipeline described above. For image URLs, the server downloads the image itself before processing, with safeguards in place to reject non-image content, cap the download size, and only follow standard web links.

## Frontend Features

The frontend is a single HTML page served by the Flask backend. It provides:

- A bot-check verification gate shown before the main app: a Google reCAPTCHA v2 checkbox that must be completed to continue. The result is verified server-side, and the verified state persists in the browser (localStorage) with no expiry until the user logs out.
- A text input for typing a claim directly.
- Microphone input using the browser's built-in speech recognition, allowing a claim to be spoken instead of typed. The microphone remains active across natural pauses in speech and is intended to keep listening until the user stops it manually, since browsers can otherwise cut recognition off after a few seconds of silence.
- Image upload and image URL submission for claims that arrive as screenshots or shared images.
- Text-to-speech playback of the result, so a returned verdict and explanation can be listened to rather than read. Playback uses a natural-sounding voice where one is available on the user's device, and stops automatically if the user switches tabs, navigates away, or submits a new claim, so it never continues speaking in the background.
- A results view showing the verdict, a confidence indicator, a highlighted portion of the claim in question where applicable, a summary of the consensus fact, a distinct explanation of why the claim was flagged, and the sources that were checked.

## Project Structure

| File | Purpose |
|---|---|
| `app.py` | Flask application. Defines the web routes for text, image upload, and image URL submissions, serves the frontend, and handles Google reCAPTCHA v2 config/verification for the access gate. |
| `main.py` | Orchestrates the full verification pipeline described above, from classification through to the final verdict. |
| `claim_extractor.py` | Classifies a claim as a news event or a general fact, and extracts a short version of it suitable for search, in a single API call. |
| `fact_check.py` | Retrieves related news articles from NewsData.io for a given claim. |
| `explain.py` | Generates a verdict and explanation using Groq, grounded in retrieved articles. |
| `gemini_checker.py` | Generates an independent second verdict using Google Gemini, grounded in the same retrieved articles. |
| `general_fact_checker.py` | Handles claims that are not tied to a specific news event, using Groq's live web search and Gemini's own knowledge as two independent checks. |
| `classifier.py` | Loads a trained Logistic Regression model and produces a fallback verdict based on writing style when no external sources can be found. |
| `image_checker.py` | Uses Gemini's vision capability to extract readable text or a claim from an uploaded image or an image URL. |
| `index.html` | The frontend interface, including the chat-style layout, microphone and speech-to-text handling, image upload, and text-to-speech playback. |

## Setup

### Requirements

- Python 3.9 or later
- A Groq API key
- A Google Gemini API key
- A NewsData.io API key
- A Google reCAPTCHA v2 site key and secret key (free — register at [google.com/recaptcha/admin](https://www.google.com/recaptcha/admin); the app falls back to Google's public test keys if none are set, which is fine for local development but must be replaced before deploying publicly)

### Installation

1. Install the required Python packages:

   ```
   pip install flask groq requests python-dotenv joblib numpy scikit-learn flask-cors flask-limiter
   ```

2. Create a `.env` file in the project root with the following entries:

   ```
   GROQ_API_KEY=your_groq_api_key
   GEMINI_API_KEY=your_gemini_api_key
   NEWSDATA_API_KEY=your_newsdata_api_key
   RECAPTCHA_SITE_KEY=your_recaptcha_site_key
   RECAPTCHA_SECRET_KEY=your_recaptcha_secret_key
   ```

3. Ensure a trained model and vectorizer are available at `model/fake_news_model.pkl` and `model/vectorizer.pkl`. These are used by the fallback classifier and are not included in this repository.

4. Run the application:

   ```
   python app.py
   ```

   The server will start on port 5000 by default.

## API Endpoints

### `POST /check`

Accepts a JSON body with a `text` field containing the claim to be checked, and returns the verdict as JSON.

### `POST /check-image`

Accepts a multipart form upload with an `image` field. The claim text is first extracted from the image and then checked using the same pipeline as `/check`. The extracted text is included in the response.

### `POST /check-image-url`

Accepts a JSON body with a `url` field pointing directly to an image. The image is downloaded, the claim text is extracted, and the result is returned in the same way as `/check-image`.

### `GET /recaptcha-config`

Returns the public reCAPTCHA site key so the frontend can render the verification widget.

### `POST /verify-recaptcha`

Accepts a JSON body with a `token` field (the response token from the completed reCAPTCHA widget). Verifies the token against Google's siteverify API and returns `{"success": true}` on success, or an error message on failure. Rate-limited to 5 requests per minute per IP.

## Limitations

The system depends on the availability and accuracy of third-party APIs, and its verdicts are only as reliable as the sources it is able to retrieve. Claims about very recent events may not yet be covered by any indexed article, in which case the result falls back to the style-based classifier, which does not verify the claim against real-world facts and should be treated with appropriate caution. The image-reading step depends on the text in an image being clear enough to extract; low-resolution or heavily stylized images may not be read correctly.

## Possible Future Improvements

- Caching recent verdicts for identical or near-identical claims to reduce repeated API calls.
- Expanding language support beyond English for both speech input and claim checking.
- Adding a user-facing history view backed by persistent storage rather than local session state alone.
- Periodically retraining the fallback classifier on more recent labeled data.

## Author

Mayank Singh Rawat
