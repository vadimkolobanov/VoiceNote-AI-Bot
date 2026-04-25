import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';

/// S11 — Захват момента (PRODUCT_PLAN.md §2.7).
///
/// M5: текстовый ввод как fallback (надёжный путь). Реальная voice-запись
/// (`record` package + on-device STT) — M5.5, в отдельной под-фиче.
/// Кнопка микрофона показывает плашку «голос подключим скоро».
class VoiceCaptureScreen extends ConsumerStatefulWidget {
  const VoiceCaptureScreen({super.key});

  @override
  ConsumerState<VoiceCaptureScreen> createState() => _VoiceCaptureScreenState();
}

class _VoiceCaptureScreenState extends ConsumerState<VoiceCaptureScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat(reverse: true);

  final _textCtl = TextEditingController();
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    HapticFeedback.mediumImpact();
  }

  @override
  void dispose() {
    _pulse.dispose();
    _textCtl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final text = _textCtl.text.trim();
    if (text.isEmpty) {
      _toast('Напиши что-нибудь.');
      return;
    }
    setState(() => _busy = true);
    try {
      final create = ref.read(createMomentProvider);
      await create(rawText: text, source: 'text');
      if (mounted) {
        HapticFeedback.lightImpact();
        context.pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Запомнил.')),
        );
      }
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (e) {
      _toast('$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      backgroundColor: MX.bgBase,
      body: SafeArea(
        child: Column(
          children: [
            // ── close ────────────────────────────────────────────────
            Align(
              alignment: Alignment.topRight,
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: IconButton(
                  icon: const Icon(Icons.close, color: MX.fgMuted, size: 28),
                  onPressed: _busy ? null : () => context.pop(),
                ),
              ),
            ),

            const SizedBox(height: 8),

            // ── pulse mic (визуальный, без записи) ────────────────────
            AnimatedBuilder(
              animation: _pulse,
              builder: (context, child) {
                final scale = 1 + (_pulse.value * 0.08);
                return Transform.scale(scale: scale, child: child);
              },
              child: GestureDetector(
                onTap: _busy
                    ? null
                    : () {
                        HapticFeedback.mediumImpact();
                        _toast('Голосовой ввод подключим в M5.5. Пока — текстом.');
                      },
                child: Container(
                  width: 120,
                  height: 120,
                  decoration: BoxDecoration(
                    gradient: MX.brandGradient,
                    shape: BoxShape.circle,
                    boxShadow: MX.fabGlow,
                  ),
                  child: const Icon(Icons.mic, size: 56, color: Colors.white),
                ),
              ),
            ),
            const SizedBox(height: 18),
            Text('Расскажи мне', style: t.textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              'Я разложу текст по полочкам сам.',
              style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
            ),

            const SizedBox(height: 24),

            // ── text field ───────────────────────────────────────────
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: TextField(
                  controller: _textCtl,
                  autofocus: true,
                  maxLines: null,
                  expands: true,
                  enabled: !_busy,
                  textCapitalization: TextCapitalization.sentences,
                  textAlignVertical: TextAlignVertical.top,
                  style: t.textTheme.bodyLarge,
                  decoration: InputDecoration(
                    hintText: 'Например: завтра в 10 встреча с Аней по поводу макетов',
                    hintStyle: t.textTheme.bodyMedium?.copyWith(color: MX.fgFaint),
                    filled: true,
                    fillColor: MX.surfaceOverlay,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(MX.rMd),
                      borderSide: const BorderSide(color: MX.line),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(MX.rMd),
                      borderSide: const BorderSide(color: MX.accentAi),
                    ),
                    contentPadding: const EdgeInsets.all(16),
                  ),
                ),
              ),
            ),

            // ── save ─────────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
              child: SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton(
                  onPressed: _busy ? null : _save,
                  child: Text(
                    _busy ? 'Сохраняю…' : 'Сохранить',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
