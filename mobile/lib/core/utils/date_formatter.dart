import 'package:intl/intl.dart';

abstract final class DateFormatter {
  static final _dayMonth = DateFormat('d MMMM', 'ru');
  static final _fullDate = DateFormat('d MMMM yyyy', 'ru');
  static final _time = DateFormat.Hm('ru');
  static final _shortDayMonth = DateFormat('d MMM', 'ru');

  static String dayMonth(DateTime date) => _dayMonth.format(date);
  static String shortDayMonth(DateTime date) => _shortDayMonth.format(date);
  static String fullDate(DateTime date) => _fullDate.format(date);
  static String time(DateTime date) => _time.format(date);

  static String relative(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);
    if (diff.inSeconds < 60) return 'только что';
    if (diff.inMinutes < 60) return '${diff.inMinutes} мин. назад';
    if (diff.inHours < 24) return '${diff.inHours} ч. назад';
    if (diff.inDays == 1) return 'вчера';
    if (diff.inDays < 7) return '${diff.inDays} дн. назад';
    return shortDayMonth(date);
  }

  static String smartDate(DateTime date) {
    final now = DateTime.now();
    final d = DateTime(date.year, date.month, date.day);
    final today = DateTime(now.year, now.month, now.day);
    if (d == today) return 'Сегодня, ${time(date)}';
    final diff = d.difference(today).inDays;
    if (diff == 1) return 'Завтра, ${time(date)}';
    if (diff == -1) return 'Вчера, ${time(date)}';
    return '${dayMonth(date)}, ${time(date)}';
  }
}
