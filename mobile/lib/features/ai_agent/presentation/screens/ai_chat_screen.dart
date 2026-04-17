import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/features/ai_agent/application/ai_chat_controller.dart';
import 'package:voicenote_ai/features/ai_agent/presentation/widgets/chat_bubble.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/payments/presentation/screens/paywall_screen.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

class AiChatScreen extends ConsumerStatefulWidget {
  const AiChatScreen({super.key});

  @override
  ConsumerState<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends ConsumerState<AiChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty) return;
    _input.clear();
    try {
      await ref.read(aiChatProvider.notifier).send(text);
      _scrollToBottom();
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.statusCode == 402 || e.isForbidden) {
        context.push(AppRoutes.paywall);
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent + 100,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(sessionControllerProvider);
    final isVip = session.user?.isVip ?? false;

    if (!isVip) {
      return const PaywallScreen(inline: true);
    }

    final state = ref.watch(aiChatProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Агент'),
        actions: [
          IconButton(
            tooltip: 'Память',
            icon: const Icon(Icons.psychology_alt_outlined),
            onPressed: () => context.push(AppRoutes.memoryFacts),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Builder(
              builder: (_) {
                if (state.isLoadingHistory) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (state.messages.isEmpty) {
                  return const EmptyStateView(
                    icon: Icons.auto_awesome_outlined,
                    title: 'Начните разговор',
                    subtitle: 'Задайте вопрос по вашим заметкам или просто о жизни',
                  );
                }
                return ListView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: state.messages.length + (state.isSending ? 1 : 0),
                  itemBuilder: (_, i) {
                    if (i == state.messages.length) {
                      return const TypingBubble();
                    }
                    return ChatBubble(message: state.messages[i]);
                  },
                );
              },
            ),
          ),
          Material(
            elevation: 8,
            shadowColor: Colors.black.withValues(alpha: 0.06),
            color: Theme.of(context).colorScheme.surface,
            child: SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _input,
                        minLines: 1,
                        maxLines: 4,
                        textCapitalization: TextCapitalization.sentences,
                        decoration: const InputDecoration(
                          hintText: 'Спросите что-нибудь…',
                        ),
                        onSubmitted: (_) => _send(),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton.filled(
                      onPressed: state.isSending ? null : _send,
                      icon: const Icon(Icons.send_rounded),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
