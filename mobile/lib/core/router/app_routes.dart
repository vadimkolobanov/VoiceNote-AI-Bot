/// Canonical route paths used across the app.
abstract final class AppRoutes {
  static const splash = '/';
  static const login = '/login';

  // Shell tabs
  static const notes = '/notes';
  static const habits = '/habits';
  static const agent = '/agent';
  static const profile = '/profile';

  // Pushed screens
  static const createNote = '/notes/new';
  static const noteDetail = '/notes/:id';
  static const shopping = '/shopping';
  static const birthdays = '/birthdays';
  static const paywall = '/paywall';
  static const payment = '/payment';
  static const settings = '/settings';
  static const memoryFacts = '/agent/memory';
  static const achievements = '/profile/achievements';

  static String noteDetailFor(int id) => '/notes/$id';
}
