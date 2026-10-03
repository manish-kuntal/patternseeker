# PATTERN Android

## Emulator

```powershell
flutter pub get
flutter run --dart-define=PATTERN_API=http://10.0.2.2:8000 --dart-define=PATTERN_KEY=change-me
```

## Physical phone

Find laptop IP:

```powershell
ipconfig
```

Then:

```powershell
flutter run --dart-define=PATTERN_API=http://YOUR_LAPTOP_IP:8000 --dart-define=PATTERN_KEY=change-me
```

Allow Python/port 8000 through Windows Firewall for private LAN testing if required.

The app currently sends a privacy-filtered heartbeat and registers the device. The same backend is ready for future opt-in Android UsageStats events.
