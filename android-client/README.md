# PhoneCase254 Android client

This Android client opens the live PhoneCase254 customer store in a secure WebView. It keeps the existing Django website as the single source of truth for accounts, products, stock, cart, wishlist, checkout, M-Pesa, orders, invoices, reviews, and Nova AI.

## Open and run

1. Open this `android-client` folder in Android Studio.
2. Allow Gradle to sync.
3. Run on an Android device or emulator with internet access.

The app currently points to:
`https://phonecase254.onrender.com/`

For local testing with the Android emulator, change `STORE_URL` in `app/build.gradle.kts` to `http://10.0.2.2:8000/` and temporarily allow cleartext traffic in the manifest.
