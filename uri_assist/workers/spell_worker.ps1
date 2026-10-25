# Writing Intelligence spelling worker (plan 16 WI-A). Windows Spell Checking API (ISpellCheckerFactory, part of
# Windows 8 and later; nothing is installed). JSON lines on stdin and stdout, same protocol as the Office workers:
#   start                                 -> {"ok": true, "ready": true}
#   {"id", "op": "check", "text", "lang"} -> {id, ok, lang, errors: [{start, length, word, action, replacement,
#                                             suggestions: [..up to 5]}]}   (start/length in UTF-16 code units)
#   {"id", "op": "quit"}
# action: 1 = get suggestions, 2 = replace (autocorrect), 3 = delete (repeated word). The worker never adds words
# to the user's Windows dictionary and never writes anything; it only reads the text it is given.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
try {
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
namespace UriWriting {
  [ComImport, Guid("8E018A9D-2415-4677-BF08-794EA61F94BB"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface ISpellCheckerFactory {
    [return: MarshalAs(UnmanagedType.Interface)] object get_SupportedLanguages();
    int IsSupported([MarshalAs(UnmanagedType.LPWStr)] string languageTag);
    [return: MarshalAs(UnmanagedType.Interface)] ISpellChecker CreateSpellChecker([MarshalAs(UnmanagedType.LPWStr)] string languageTag);
  }
  [ComImport, Guid("B6FD0B71-E2BC-4653-8D05-F197E412770B"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface ISpellChecker {
    [return: MarshalAs(UnmanagedType.LPWStr)] string get_LanguageTag();
    [return: MarshalAs(UnmanagedType.Interface)] IEnumSpellingError Check([MarshalAs(UnmanagedType.LPWStr)] string text);
    [return: MarshalAs(UnmanagedType.Interface)] IEnumString Suggest([MarshalAs(UnmanagedType.LPWStr)] string word);
  }
  [ComImport, Guid("803E3BD4-2828-4410-8290-418D1D73C762"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IEnumSpellingError {
    [PreserveSig] int Next([MarshalAs(UnmanagedType.Interface)] out ISpellingError value);
  }
  [ComImport, Guid("B7C82D61-FBE8-4B47-9B27-6C0D2E0DE0A3"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface ISpellingError {
    uint get_StartIndex(); uint get_Length(); int get_CorrectiveAction();
    [return: MarshalAs(UnmanagedType.LPWStr)] string get_Replacement();
  }
  [ComImport, Guid("00000101-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IEnumString {
    [PreserveSig] int Next(int celt, out IntPtr rgelt, out int pceltFetched);
  }
  public class Err { public int start; public int length; public string word; public int action; public string replacement; public string[] suggestions; }
  public static class Checker {
    static readonly Dictionary<string, ISpellChecker> cache = new Dictionary<string, ISpellChecker>();
    static ISpellCheckerFactory factory;
    public static string Resolve(string tag) {
      if (factory == null) factory = (ISpellCheckerFactory)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("7AB36653-1796-484B-BDFA-E74F1DB7C1DC")));
      foreach (var t in new[] { tag, "en-IN", "en-GB", "en-US" }) {
        if (!String.IsNullOrEmpty(t) && factory.IsSupported(t) != 0) return t;
      }
      return null;
    }
    public static List<Err> Run(string tag, string text) {
      ISpellChecker c;
      if (!cache.TryGetValue(tag, out c)) { c = factory.CreateSpellChecker(tag); cache[tag] = c; }
      var res = new List<Err>();
      var e = c.Check(text); ISpellingError err;
      while (res.Count < 200 && e.Next(out err) == 0) {
        var x = new Err();
        x.start = (int)err.get_StartIndex(); x.length = (int)err.get_Length();
        x.word = text.Substring(x.start, x.length); x.action = err.get_CorrectiveAction(); x.replacement = err.get_Replacement() ?? "";
        var sugg = new List<string>();
        if (x.action == 1) {
          var en = c.Suggest(x.word); IntPtr ptr; int got;
          while (sugg.Count < 5 && en.Next(1, out ptr, out got) == 0 && got == 1 && ptr != IntPtr.Zero) {
            sugg.Add(Marshal.PtrToStringUni(ptr)); Marshal.FreeCoTaskMem(ptr);
          }
        }
        x.suggestions = sugg.ToArray();
        res.Add(x);
      }
      return res;
    }
  }
}
"@
} catch {
  [Console]::Out.WriteLine('{"ok": false, "error": "SPELL_UNAVAILABLE"}'); [Console]::Out.Flush(); exit 3
}
[Console]::Out.WriteLine('{"ok": true, "ready": true}'); [Console]::Out.Flush()
while ($true) {
  $line = [Console]::In.ReadLine()
  if ($null -eq $line) { break }
  $id = $null
  try {
    $req = ConvertFrom-Json $line
    $id = $req.id
    if ($req.op -eq 'quit') { break }
    if ($req.op -ne 'check') { $out = @{ id = $id; ok = $false; error = 'BAD_OP' } }
    else {
      $tag = [UriWriting.Checker]::Resolve([string]$req.lang)
      if ($null -eq $tag) { $out = @{ id = $id; ok = $false; error = 'SPELL_LANGUAGE_UNAVAILABLE' } }
      else {
        $errs = @([UriWriting.Checker]::Run($tag, [string]$req.text) | ForEach-Object {
          @{ start = $_.start; length = $_.length; word = $_.word; action = $_.action; replacement = $_.replacement;
             suggestions = @($_.suggestions) } })
        $out = @{ id = $id; ok = $true; lang = $tag; errors = $errs }
      }
    }
  } catch {
    $out = @{ id = $id; ok = $false; error = 'SPELL_FAILED' }
  }
  [Console]::Out.WriteLine((ConvertTo-Json $out -Compress -Depth 5)); [Console]::Out.Flush()
}
