import 'package:flutter/material.dart';
import 'chat_screen.dart';

class FreeFrameApp extends StatelessWidget {
  const FreeFrameApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFF8B8F98);
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'FreeFrame',
      themeMode: ThemeMode.system,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: seed,
          brightness: Brightness.light,
          surface: const Color(0xFFF7F7F5),
        ),
        scaffoldBackgroundColor: const Color(0xFFF7F7F5),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: seed,
          brightness: Brightness.dark,
          surface: const Color(0xFF171717),
        ),
        scaffoldBackgroundColor: const Color(0xFF111111),
      ),
      home: const ChatScreen(),
    );
  }
}
