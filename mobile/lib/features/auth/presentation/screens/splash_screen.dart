import 'package:flutter/material.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 96, height: 96,
              decoration: BoxDecoration(
                gradient: MX.brandGradient,
                borderRadius: BorderRadius.circular(MX.rXl),
                boxShadow: MX.fabGlow,
              ),
              child: const Center(
                child: Text('М',
                    style: TextStyle(
                      color: Colors.white, fontSize: 48, fontWeight: FontWeight.w700,
                    )),
              ),
            ),
            const SizedBox(height: 24),
            Text('Методекс Секретарь',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                    )),
            const SizedBox(height: 28),
            const SizedBox(
              width: 28, height: 28,
              child: CircularProgressIndicator(strokeWidth: 2, color: MX.accentAi),
            ),
          ],
        ),
      ),
    );
  }
}
