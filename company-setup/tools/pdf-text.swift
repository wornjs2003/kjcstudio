// PDF 의 글자를 그대로 꺼낸다 — 맥에 들어 있는 PDFKit 만 쓴다(설치할 것 없음).
// fetch-trade.py 가 관세청 수출입 잠정치 원문 PDF 를 읽을 때 부른다.
//   swift company-setup/tools/pdf-text.swift <파일.pdf>
import PDFKit

guard CommandLine.arguments.count > 1,
      let doc = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1])) else {
    FileHandle.standardError.write("PDF 를 못 열었습니다\n".data(using: .utf8)!)
    exit(2)
}
var out = ""
for i in 0..<doc.pageCount { out += (doc.page(at: i)?.string ?? "") + "\n" }
print(out)
