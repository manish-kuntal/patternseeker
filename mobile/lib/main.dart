import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

void main() {
  runApp(const PatternMobile());
}

class Config {
  static const api = String.fromEnvironment(
    'PATTERN_API',
    defaultValue: 'http://10.0.2.2:8000',
  );
  static const key = String.fromEnvironment(
    'PATTERN_KEY',
    defaultValue: 'change-me',
  );
}

class Api {
  Future<String> deviceId() async {
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString('pattern_device_id');

    if (id == null) {
      id = 'android-${const Uuid().v4()}';
      await prefs.setString('pattern_device_id', id);
    }

    return id;
  }

  Future<void> register() async {
    final id = await deviceId();

    final response = await http.post(
      Uri.parse('${Config.api}/api/devices'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'device_id': id,
        'name': 'PATTERN Android',
        'platform': 'android',
      }),
    );

    if (response.statusCode >= 400) {
      throw Exception('Device registration failed');
    }
  }

  Future<void> event({
    required String type,
    required Map<String, dynamic> metadata,
  }) async {
    final id = await deviceId();

    final response = await http.post(
      Uri.parse('${Config.api}/api/events'),
      headers: {
        'Content-Type': 'application/json',
        'X-Pattern-Key': Config.key,
      },
      body: jsonEncode({
        'device_id': id,
        'event_type': type,
        'source': 'android',
        'timestamp': DateTime.now().toUtc().toIso8601String(),
        'metadata': metadata,
      }),
    );

    if (response.statusCode >= 400) {
      throw Exception('Event upload failed');
    }
  }
}

class PatternMobile extends StatelessWidget {
  const PatternMobile({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'PATTERN',
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF08090C),
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.deepPurple,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const Home(),
    );
  }
}

class Home extends StatefulWidget {
  const Home({super.key});

  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  final api = Api();
  Timer? timer;

  bool running = false;
  String status = 'Collector disabled';

  Future<void> start() async {
    try {
      await api.register();
      await api.event(
        type: 'mobile_heartbeat',
        metadata: {'collector_version': '1.0.0'},
      );

      timer = Timer.periodic(
        const Duration(minutes: 5),
        (_) async {
          try {
            await api.event(
              type: 'mobile_heartbeat',
              metadata: {'collector_version': '1.0.0'},
            );
            if (mounted) {
              setState(() => status = 'Last sync: ${DateTime.now()}');
            }
          } catch (_) {
            if (mounted) {
              setState(() => status = 'Sync failed — check network');
            }
          }
        },
      );

      setState(() {
        running = true;
        status = 'Connected and collecting';
      });
    } catch (_) {
      setState(() => status = 'Unable to connect to PATTERN API');
    }
  }

  void stop() {
    timer?.cancel();
    setState(() {
      running = false;
      status = 'Collector paused';
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'PATTERN',
          style: TextStyle(
            fontWeight: FontWeight.w800,
            letterSpacing: 2,
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text(
            'Personal Behavior Intelligence',
            style: TextStyle(fontSize: 27, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            'Phone signal source for your PATTERN account.',
            style: TextStyle(color: Colors.grey.shade400),
          ),
          const SizedBox(height: 28),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Phone Collector',
                    style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 10),
                  Text(status),
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: running ? stop : start,
                    icon: Icon(running ? Icons.pause : Icons.play_arrow),
                    label: Text(running ? 'Pause' : 'Start'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Privacy',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  SizedBox(height: 10),
                  Text(
                    'This base collector does not read keystrokes, passwords, screenshots, clipboard data, messages, or file contents.',
                  ),
                  SizedBox(height: 10),
                  Text(
                    'Android UsageStats is an explicit OS-permission feature and is kept separate from this base collector.',
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
