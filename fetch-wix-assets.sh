#!/bin/bash
# Downloads the images and PDFs from the old Wix site into this folder.
# Run once from inside the `site` folder:   bash fetch-wix-assets.sh
# Safe to re-run; it skips files already downloaded.

set -u
cd "$(dirname "$0")"
mkdir -p media/autism files/afirm

IMG="https://static.wixstatic.com/media"
UGD="https://cc0eef4a-f3b4-4acb-8420-069098274fab.filesusr.com/ugd"

get () { # get <url> <destination>
  if [ -s "$2" ]; then echo "  skip  $2"; return; fi
  if curl -fsSL --retry 2 "$1" -o "$2"; then echo "  ok    $2"
  else echo "  FAIL  $2"; rm -f "$2"; fi
}

echo "Images -> media/autism/"

# --- Key Constructs During Assessments ---
get "$IMG/f59cb6_ad083aba8c6b4f82a1dd3cf18648986e~mv2.jpeg" media/autism/assessment-hero.jpeg
get "$IMG/f59cb6_510dc22264cd4fc1b96f441e4bc80f0f~mv2.png"  media/autism/behavioral-assessment.png
get "$IMG/f59cb6_5f37750d61434a3bb81e0da7a71ae1c9~mv2.png"  media/autism/statistical-significance.png
get "$IMG/f59cb6_f608c6c8051b4deb8f50cb63e3f4fb3f~mv2.png"  media/autism/percentile.png
get "$IMG/f59cb6_b130073b041740bca636d4a69a73bf4c~mv2.png"  media/autism/bell-curve.png
get "$IMG/f59cb6_17f2aed38b9a4d69b1cde4090ca0e4ce~mv2.png"  media/autism/confidence-interval.png
get "$IMG/f59cb6_a6147172ec4f434ebb5b0460dee26140~mv2.jpg"  media/autism/standard-score.jpg
get "$IMG/f59cb6_5fca22ed43e24ff4bd7b302fe6365745~mv2.png"  media/autism/range.png
get "$IMG/f59cb6_e25766175130468fbaf5a1bd867d9be4~mv2.jpg"  media/autism/criterion.jpg
get "$IMG/f59cb6_0d34e17dfad04abdbff5e7fc59ad7da5~mv2.png"  media/autism/criterion-assessments.png

# --- Key Constructs of HFA ---
get "$IMG/f59cb6_ec9c4f35cec74ecf98c8ba9c6efb0d5b~mv2.jpg"  media/autism/ableism.jpg
get "$IMG/f59cb6_340afabc446541e9b2bd54563cd9287a~mv2.jpg"  media/autism/girls-spectrum.jpg
get "$IMG/f59cb6_6f9e5bd74ffc44c09bc137655e492777~mv2.jpg"  media/autism/executive-function.jpg
get "$IMG/f59cb6_671d69e6c63b4d1a9636ecdb964d3f25~mv2.jpg"  media/autism/theory-of-mind.jpg
get "$IMG/f59cb6_3d5a3ced95b949e0a614faccbb7f2dc8~mv2.jpg"  media/autism/mind-blindness.jpg
get "$IMG/f59cb6_c7d54c6885d44a0092658230e416cccd~mv2.jpg"  media/autism/social-thinking.jpg
get "$IMG/f59cb6_aa44337ca1634c1896aed37104c56bf4~mv2.jpg"  media/autism/emotional-vulnerability.jpg
get "$IMG/f59cb6_c3d0697e3eb442f4a248e36641d71e75~mv2.jpg"  media/autism/senses.jpg
get "$IMG/f59cb6_923c723622fc4fa68e8fbee9d0f6ef01~mv2.jpg"  media/autism/giftedness.jpg
get "$IMG/f59cb6_6a7f6d2922354921828af11dca122fe6~mv2.jpg"  media/autism/meltdowns.jpg

# --- Assessment Process ---
get "$IMG/f59cb6_4e84666e10a54e65a909ef650f148ddd~mv2.png"  media/autism/aap-flowchart.png
get "$IMG/f59cb6_b571d3cf6976495390d10d9d05443897~mv2.png"  media/autism/dsm5-vs-idea.png

# --- Faith essay ---
get "$IMG/f59cb6_82795b136e8f41479a4a8ee3748bea6a~mv2.jpg"  media/autism/god-loves-the-autistic-mind.jpg
get "$IMG/f59cb6_b9f7225c85e34ca7977ed8829fcf74f7~mv2.jpg"  media/autism/fr-matthew-schneider.jpg
get "$IMG/f59cb6_fea571f6c9a24e2192efd899ce2a87f7~mv2.jpg"  media/autism/crucifix.jpg

echo "PDFs -> files/afirm/ and files/"
get "$UGD/f59cb6_c957b88013944602b679cfd5b1e79e4e.pdf" files/afirm/reinforcement.pdf
get "$UGD/f59cb6_3eba04087eb04b6a94d718b8e4c74018.pdf" files/afirm/visual-supports.pdf
get "$UGD/f59cb6_727feb5bd1af4b2ea4c614226d6e9811.pdf" files/afirm/video-modeling.pdf
get "$UGD/f59cb6_2397034fe92b4127919874506afc558c.pdf" files/afirm/response-interruption-redirection.pdf
get "$UGD/f59cb6_005356b76fe5480096e9e88b5a365a2b.pdf" files/afirm/discrete-trial-training.pdf
get "$UGD/f59cb6_a8393584438a486faa09871ce8d7e2cf.pdf" files/afirm/aac.pdf
get "$UGD/f59cb6_d7edf5e2c5d84ba0b66a14b3de50432b.pdf" files/aap-autism-assessment-flowchart.pdf
get "$UGD/f59cb6_3a5e072b6fef4f919b81db048abe97fc.pdf" files/executive-functioning-children-adolescents.pdf

echo
echo "Done. Anything marked FAIL needs to be saved by hand from the Wix editor."
