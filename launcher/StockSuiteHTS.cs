using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Threading;
using System.Windows.Forms;

namespace StockSuiteLauncher
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();

            string root = AppDomain.CurrentDomain.BaseDirectory;
            string url = "http://127.0.0.1:8765/";
            string appScript = Path.Combine(root, "app", "stock_suite_app.py");
            string defaultUserDataDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "CodexStock",
                "data"
            );
            string bundledPython = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                ".cache",
                "codex-runtimes",
                "codex-primary-runtime",
                "dependencies",
                "python",
                "python.exe"
            );

            if (!File.Exists(appScript))
            {
                MessageBox.Show(
                    "앱 파일을 찾을 수 없습니다.\n\n" + appScript,
                    "주식 스튜디오 실행 실패",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return;
            }

            if (!File.Exists(bundledPython))
            {
                MessageBox.Show(
                    "실행에 필요한 Python 런타임을 찾을 수 없습니다.\n\n" + bundledPython,
                    "주식 스튜디오 실행 실패",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return;
            }

            try
            {
                if (!IsServerReady(url))
                {
                    ProcessStartInfo server = new ProcessStartInfo();
                    server.FileName = bundledPython;
                    server.Arguments = "\"app\\stock_suite_app.py\" --host 127.0.0.1 --port 8765";
                    server.WorkingDirectory = root;
                    server.UseShellExecute = false;
                    server.CreateNoWindow = true;
                    Directory.CreateDirectory(defaultUserDataDir);
                    if (!server.EnvironmentVariables.ContainsKey("CODEXSTOCK_USER_DATA_DIR")
                        || String.IsNullOrWhiteSpace(server.EnvironmentVariables["CODEXSTOCK_USER_DATA_DIR"]))
                    {
                        server.EnvironmentVariables["CODEXSTOCK_USER_DATA_DIR"] = defaultUserDataDir;
                    }
                    Process.Start(server);

                    for (int attempt = 0; attempt < 25; attempt++)
                    {
                        if (IsServerReady(url))
                        {
                            break;
                        }
                        Thread.Sleep(200);
                    }
                }

                OpenUrl(url);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "실행 중 오류가 발생했습니다.\n\n" + ex.Message,
                    "주식 스튜디오 실행 실패",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }

        private static bool IsServerReady(string url)
        {
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
                request.Method = "GET";
                request.Timeout = 500;
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                {
                    return (int)response.StatusCode >= 200 && (int)response.StatusCode < 500;
                }
            }
            catch
            {
                return false;
            }
        }

        private static void OpenUrl(string url)
        {
            ProcessStartInfo browser = new ProcessStartInfo();
            browser.FileName = url;
            browser.UseShellExecute = true;
            Process.Start(browser);
        }
    }
}
