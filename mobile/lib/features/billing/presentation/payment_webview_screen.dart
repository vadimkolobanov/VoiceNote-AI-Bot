import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/billing/data/billing_repository.dart';

/// S13 — WebView для оплаты YooKassa (PRODUCT_PLAN.md §8.3).
///
/// Принимает либо реальный confirmation_url (https://yoomoney.ru/...) — тогда
/// показывает встроенный браузер до тех пор, пока URL не вернётся на
/// `voicenote://payment/success`. Либо mock deeplink
/// `voicenote://billing/mock?id=...` — тогда показывает «фейковый чекаут»
/// с одной кнопкой «Я заплатил».
class PaymentWebViewScreen extends ConsumerStatefulWidget {
  const PaymentWebViewScreen({
    super.key,
    required this.confirmationUrl,
    required this.externalId,
    required this.isMock,
  });

  final String confirmationUrl;
  final String externalId;
  final bool isMock;

  @override
  ConsumerState<PaymentWebViewScreen> createState() => _PaymentWebViewState();
}

class _PaymentWebViewState extends ConsumerState<PaymentWebViewScreen> {
  WebViewController? _ctl;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    if (!widget.isMock) {
      _ctl = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setNavigationDelegate(
          NavigationDelegate(
            onNavigationRequest: (req) async {
              final url = req.url;
              if (url.startsWith('voicenote://payment')) {
                // YooKassa завершила redirect → закрываем WebView
                // и предоставляем UI «проверяем, поллим status».
                await _onPaid();
                return NavigationDecision.prevent;
              }
              return NavigationDecision.navigate;
            },
          ),
        )
        ..loadRequest(Uri.parse(widget.confirmationUrl));
    }
  }

  Future<void> _onPaid() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      // Полл /billing/status пока is_pro=true. До 30 секунд (15 попыток × 2с).
      final repo = ref.read(billingRepositoryProvider);
      for (var i = 0; i < 15; i++) {
        await Future.delayed(const Duration(seconds: 2));
        final s = await repo.status();
        if (s.isPro) {
          await ref.read(sessionControllerProvider.notifier).refreshUser();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Добро пожаловать в Pro.')),
            );
            context.pop();
          }
          return;
        }
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Оплата ещё в обработке. Если всё ок — Pro появится в Профиле через минуту.',
            ),
          ),
        );
        context.pop();
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _mockPay() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await ref.read(billingRepositoryProvider).mockConfirm(widget.externalId);
      await ref.read(sessionControllerProvider.notifier).refreshUser();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Mock-оплата прошла. Pro активен.')),
        );
        context.pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: MX.bgBase,
      appBar: AppBar(
        backgroundColor: MX.bgBase,
        surfaceTintColor: Colors.transparent,
        title: const Text('Оплата'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: _busy ? null : () => context.pop(),
        ),
      ),
      body: widget.isMock ? _buildMock(context) : _buildWebView(),
    );
  }

  Widget _buildWebView() {
    if (_ctl == null) return const SizedBox.shrink();
    return Stack(
      children: [
        WebViewWidget(controller: _ctl!),
        if (_busy)
          const ColoredBox(
            color: Color(0x88000000),
            child: Center(
              child: CircularProgressIndicator(color: MX.accentAi),
            ),
          ),
      ],
    );
  }

  Widget _buildMock(BuildContext context) {
    final t = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 32),
          Text('Mock-режим', style: t.textTheme.titleLarge),
          const SizedBox(height: 8),
          Text(
            'Backend стоит в YK_MODE=mock — реальный запрос в YooKassa не уйдёт. '
            'Это для проверки UI-flow до получения test-ключей. '
            'Жми «Я заплатил», чтобы имитировать успех.',
            style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
          ),
          const SizedBox(height: 32),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: MX.surfaceOverlay,
              borderRadius: BorderRadius.circular(MX.rMd),
              border: Border.all(color: MX.line),
            ),
            child: Row(
              children: [
                const Icon(Icons.bug_report_outlined, color: MX.accentAi),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'external_id: ${widget.externalId}',
                    style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
                  ),
                ),
              ],
            ),
          ),
          const Spacer(),
          SizedBox(
            width: double.infinity,
            height: 52,
            child: FilledButton(
              onPressed: _busy ? null : _mockPay,
              child: Text(
                _busy ? 'Подтверждаю…' : 'Я заплатил',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              ),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: _busy ? null : () => context.pop(),
              child: const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('Отмена'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
